import contextlib
import ftplib
import ipaddress
import os
import socket
import time
from abc import abstractmethod
from collections import OrderedDict
from ftplib import FTP
from threading import Thread
from time import sleep
from typing import TYPE_CHECKING, Callable, Generic, Optional, Union

import ingenialogger
from multiping import multi_ping
from typing_extensions import TypeVar, override

from ingenialink.constants import DEFAULT_ETH_CONNECTION_TIMEOUT
from ingenialink.ethernet.resources import BASIC_ETHERNET_V2_XDF
from ingenialink.ethernet.servo import EthernetServo, EthernetServoBase
from ingenialink.ethernet.tsn.ipv6_discovery import (
    discover_ipv6_devices,
)
from ingenialink.ethernet.tsn.sdcp.connection import (
    DEFAULT_SDCP_TIMEOUT_S,
)
from ingenialink.ethernet.tsn.sdcp.identification import (
    identify_sdcp_node,
)
from ingenialink.ethernet.tsn.sdcp.node import SDCPNode
from ingenialink.ethernet.tsn.sdcp.servo import SDCPServo
from ingenialink.exceptions import ILError, ILFirmwareLoadError
from ingenialink.network import (
    NetDevEvt,
    NetProt,
    NetState,
    Network,
    ServoTarget,
    SlaveInfo,
)
from ingenialink.servo import Servo
from ingenialink.utils.udp import UDP

if TYPE_CHECKING:
    from ingenialink.node import NodeIdentity

logger = ingenialogger.get_logger(__name__)

FTP_SESSION_OK_CODE = "220"
FTP_LOGIN_OK_CODE = "230"
FTP_FILE_TRANSFER_OK_CODE = "226"
FTP_CLOSE_OK_CODE = "221"
FTP_CLOSE_TIMEOUT_S = 120

CMD_CHANGE_CPU = 0x67E4

MAX_NUM_UNSUCCESSFUL_PINGS = 3

MAX_NUMBER_OF_SCAN_TRIES = 2
SCAN_CONNECTION_TIMEOUT = 0.5

DEFAULT_FIRMWARE_RECOVERY_TIMEOUT_S = 30.0
FIRMWARE_RECOVERY_POLL_INTERVAL_S = 1.0


EthernetServoT = TypeVar("EthernetServoT", bound=EthernetServoBase, default=EthernetServoBase)


class NetStatusListener(Thread, Generic[EthernetServoT]):
    """Network status listener thread to check if the drive is alive.

    Args:
        network: Network instance of the Ethernet communication.

    """

    def __init__(
        self, network: "EthernetNetworkBase[EthernetServoT]", refresh_time: float = 0.25
    ) -> None:
        super().__init__()
        self.__network = network
        self.__refresh_time = refresh_time
        self.__stop = False

    def process(self) -> None:
        """Process network status for all servos.

        This method checks the status of all servos in the network and notifies
        subscribers of any state changes (connection/disconnection).
        """
        for servo in self.__network.servos:
            if not isinstance(servo, (EthernetServo, SDCPServo)):
                # Virtual ethernet servos do not yet implement ip address attr
                # https://novantamotion.atlassian.net/browse/INGK-1286
                continue

            servo_state = self.__network.get_servo_state(servo)
            is_servo_alive = servo.is_alive(attemps=MAX_NUM_UNSUCCESSFUL_PINGS)
            if servo_state == NetState.CONNECTED and not is_servo_alive:
                self.__network._transition_servo_state(servo, NetDevEvt.REMOVED)
            if (
                servo_state == NetState.DISCONNECTED
                and is_servo_alive
                and self.__network.recover_from_disconnection(servo)
            ):
                self.__network._transition_servo_state(servo, NetDevEvt.ADDED)

    def run(self) -> None:
        """Check the network status."""
        while not self.__stop:
            try:
                self.process()
            except Exception as e:
                logger.exception(f"Exception occurred while processing network status: {e}")
            time.sleep(self.__refresh_time)

    def stop(self) -> None:
        """Stop the listener."""
        self.__stop = True


class EthernetNetworkBase(Generic[EthernetServoT], Network[Servo]):
    """Network for all Ethernet communications.

    Args:
        subnet: The subnet in CIDR notation.

    """

    def __init__(self, subnet: Optional[str] = None) -> None:
        super().__init__()
        self.__subnet: Optional[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]
        if subnet is not None:
            self.__subnet = ipaddress.ip_network(subnet, strict=False)
        else:
            self.__subnet = None
        self.__listener_net_status: Optional[NetStatusListener[EthernetServoT]] = None

    @staticmethod
    def load_firmware(
        fw_file: str, target: str = "192.168.2.22", ftp_user: str = "", ftp_pwd: str = ""
    ) -> None:
        """Loads a given firmware file to the target slave.

        .. warning ::
            It is needed to disconnect the drive(:func:`disconnect_from_slave`)
            after loading the firmware since the `Servo` object's data will
            become obsolete.

        Args:
            fw_file: Path to the firmware file to be loaded.
            target: IP of the target slave.
            ftp_user: FTP user to connect with.
            ftp_pwd: FTP password for the given user.

        Raises:
            FileNotFoundError: If the file is not found.
            ILFirmwareLoadError: If it is not possible to create the FTP session.
            ILFirmwareLoadError: If it is not possible to open the FTP session.
            ILFirmwareLoadError: If it is unable to login the FTP session.
            ILFirmwareLoadError: If it is unable to load the FW file through FTP.

        """
        if not os.path.isfile(fw_file):
            raise FileNotFoundError(f"Could not find {fw_file}.")

        # Start a FTP session. Drive must be in BOOT mode.
        logger.info("Starting FTP session...")
        with FTP() as ftp:
            try:
                ftp_output = ftp.connect(target)
            except ConnectionError as e:
                raise ILFirmwareLoadError("Unable to create the FTP session") from e
            logger.info(ftp_output)
            if FTP_SESSION_OK_CODE not in ftp_output:
                raise ILFirmwareLoadError("Unable to open the FTP session")
            # Login into FTP session.
            logger.info("Logging into FTP session...")
            try:
                ftp_output = ftp.login(ftp_user, ftp_pwd)
            except ftplib.error_perm as e:
                raise ILFirmwareLoadError("Unable to login the FTP session") from e
            logger.info(ftp_output)
            if FTP_LOGIN_OK_CODE not in ftp_output:
                raise ILFirmwareLoadError("Unable to login the FTP session")
            # Load file through FTP.
            logger.info("Uploading firmware file...")
            ftp.set_pasv(False)
            try:
                with open(fw_file, "rb") as file:
                    ftp_output = ftp.storbinary(f"STOR {os.path.basename(file.name)}", file)
            except ftplib.error_temp as e:
                raise ILFirmwareLoadError("Unable to load the FW file through FTP.") from e
            logger.info(ftp_output)
            if FTP_FILE_TRANSFER_OK_CODE not in ftp_output:
                raise ILFirmwareLoadError("Unable to load the FW file through FTP")
            if ftp.sock is not None:
                ftp.sock.settimeout(FTP_CLOSE_TIMEOUT_S)  # Avoid quit/close getting stuck
        logger.info("FTP session closed.")

    @staticmethod
    def load_firmware_moco(node: int, subnode: int, ip: str, port: int, moco_file: str) -> None:
        """Update MOCO firmware through UDP protocol.

        Args:
            node: Network node.
            subnode: Drive subnode.
            ip: Drive address IP.
            port: Drive port.
            moco_file: Path to the firmware file.

        Raises:
            ILFirmwareLoadError: The firmware load process fails
                with an error message.
        """
        upd = UDP(port, ip)

        if not moco_file or not os.path.isfile(moco_file):
            raise ILFirmwareLoadError("File not found")
        with open(moco_file) as moco_in:
            logger.info("Loading firmware...")
            try:
                for line in moco_in:
                    words = line.split()

                    # Get command and address
                    cmd = int(words[1] + words[0], 16)
                    data = b""
                    data_start_byte = 2
                    while data_start_byte in range(data_start_byte, len(words)):
                        # Load UDP data
                        data += bytes([int(words[data_start_byte], 16)])
                        data_start_byte += 1

                    # Send message
                    upd.raw_cmd(node, subnode, cmd, data)

                    if cmd == CMD_CHANGE_CPU:
                        sleep(1)

                logger.info("Bootload process succeeded")
            except ftplib.error_temp as e:
                logger.error(e)
                raise ILFirmwareLoadError("Firewall might be blocking the access.")
            except Exception as e:
                logger.error(e)
                raise ILFirmwareLoadError("Error during bootloader process.")

    def _scan_slaves(self) -> list[str]:
        """Ping all the network IPs.

        Returns:
            List containing the IPs that responded to the ping request.

        """
        if self.__subnet is None:
            return []
        hosts_ips = [str(ip) for ip in self.__subnet]
        # The scanning process can fail sometimes. Retry
        # Check https://github.com/romana/multi-ping/issues/19
        detected_slaves: dict[str, int] = {}
        for _ in range(MAX_NUMBER_OF_SCAN_TRIES):
            with contextlib.suppress(OSError):
                ping_responses, _ = multi_ping(hosts_ips, timeout=1, ignore_lookup_errors=True)
                detected_slaves.update(ping_responses)
        return list(detected_slaves.keys())

    @abstractmethod
    def _create_servo(
        self,
        *,
        target: str,
        dictionary: str,
        port: int,
        connection_timeout: float,
        servo_status_listener: bool,
        is_eoe: bool,
        disconnect_callback: Optional[Callable[[Servo], None]],
    ) -> EthernetServoT:
        """Create a servo for this Ethernet network implementation."""
        raise NotImplementedError

    def scan_slaves(self) -> list[str]:  # type: ignore [override]
        """Scan drives connected to the network.

        Returns:
            List containing the IPs of the detected drives.

        """
        detected_slaves = self.scan_slaves_info()
        return list(detected_slaves.keys())

    @override
    def scan_slaves_info(self) -> OrderedDict[str, SlaveInfo]:  # type: ignore [override]
        slave_info: OrderedDict[str, SlaveInfo] = OrderedDict()
        slaves = self._scan_slaves()
        for slave_id in slaves:
            with contextlib.suppress(ILError):
                slave_info[slave_id] = self._get_servo_info_for_scan(slave_id)
        return slave_info

    def connect_to_slave(
        self,
        target: str,
        dictionary: str,
        port: int = 1061,
        connection_timeout: float = DEFAULT_ETH_CONNECTION_TIMEOUT,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
        is_eoe: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ) -> EthernetServoT:
        """Connects to a slave through the given network settings.

        Args:
            target: IP of the target slave.
            dictionary: Path to the target dictionary file.
            port: Port to connect to the slave.
            connection_timeout: Time in seconds of the connection timeout.
            servo_status_listener: Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener: Toggle the listener of the network
                status, connection and disconnection.
            is_eoe: True if communication is EoE. ``False`` by default.
            disconnect_callback: Callback function to be called when the servo is disconnected.
                If not specified, no callback will be called.

        Returns:
            EthernetServo: Instance of the servo connected.

        Raises:
            ILError: If the drive is not found.
        """
        servo = self._create_servo(
            target=target,
            dictionary=dictionary,
            port=port,
            connection_timeout=connection_timeout,
            servo_status_listener=servo_status_listener,
            is_eoe=is_eoe,
            disconnect_callback=disconnect_callback,
        )
        try:
            servo.get_state()
        except ILError as e:
            servo.stop_status_listener()
            raise ILError(f"Drive not found in IP {target}.") from e
        self.servos.append(servo)
        self._set_servo_state(target, NetState.CONNECTED)

        if net_status_listener:
            self.start_status_listener()
        return servo

    def disconnect_from_slave(self, servo: Servo) -> None:
        """Disconnect a servo from the network.

        Args:
            servo: Instance of the connected servo.

        Raises:
            ValueError: If the servo is not managed by the network or its type is
                unsupported.
        """
        if servo not in self.servos:
            raise ValueError("The servo is not managed by this network")

        if not isinstance(servo, EthernetServoBase):
            raise ValueError("Unsupported servo type")

        servo.stop_status_listener()
        self.close_socket(servo.socket)
        self._set_servo_state(servo, NetState.DISCONNECTED)
        self._remove_servo(servo)
        # Notify that disconnect_from_slave has been called
        servo._disconnect_event_publisher.notify(servo)

    @staticmethod
    def close_socket(sock: socket.socket) -> None:
        """Closes the established network socket."""
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()

    def start_status_listener(self) -> None:
        """Start monitoring network events (CONNECTION/DISCONNECTION)."""
        if self.__listener_net_status is None:
            listener = NetStatusListener[EthernetServoT](self)
            listener.start()
            self.__listener_net_status = listener

    def stop_status_listener(self) -> None:
        """Stops the NetStatusListener from listening to the drive."""
        if self.__listener_net_status is not None:
            self.__listener_net_status.stop()
            self.__listener_net_status.join()
        self.__listener_net_status = None

    @override
    def recover_from_disconnection(self, servo: Optional[Servo] = None) -> bool:
        """Recover the communication with a servo after a disconnection.

        This method attempts to re-establish communication with a servo
        that has been previously disconnected. It checks if the servo
        is responding again.

        Args:
            servo: The servo to recover communication with.

        Returns:
            True if communication with the servo is recovered, False otherwise.

        Raises:
            ValueError: If the servo argument is None or not an Ethernet or SDCP Servo instance.
        """
        if servo is None or not isinstance(servo, (EthernetServo, SDCPServo)):
            raise ValueError("An Ethernet or SDCP Servo instance must be provided for recovery.")

        if servo.is_alive(attemps=MAX_NUM_UNSUCCESSFUL_PINGS):
            logger.info(f"Communication with servo at {servo.target} recovered.")
            return True

        logger.warning(f"Failed to recover communication with servo at {servo.target}.")
        return False

    def get_servo_state(self, servo_id: ServoTarget) -> NetState:
        """Get the state of a servo that's a part of network.

        The state indicates if the servo is connected or disconnected.

        Args:
            servo_id: The servo target or servo instance.

        Returns:
            The servo's state.

        Raises:
            ValueError: if the servo ID is not a string or a servo instance.
        """
        if not isinstance(servo_id, (str, Servo)):
            raise ValueError("The servo ID must be a string or an instance of Servo.")
        return super().get_servo_state(servo_id)

    def _get_servo_info_for_scan(self, ip_address: str) -> SlaveInfo:
        """Get the product code and revision number of a drive.

        It's used for the scan_slaves_info method.

        Returns:
            product code and revision number.

        Raises:
            TypeError: if the product code type is not an integer.
        """
        servo = self.connect_to_slave(
            ip_address, BASIC_ETHERNET_V2_XDF, connection_timeout=SCAN_CONNECTION_TIMEOUT
        )
        try:
            product_code = servo.read("DRV_ID_PRODUCT_CODE_COCO", subnode=0)
        except ILError:
            logger.error(f"The product code cannot be read from the drive with IP: {ip_address}.")
            product_code = None
        if not isinstance(product_code, int):
            raise TypeError(f"Expected product code type to be int, got {type(product_code)}")
        try:
            revision_number = servo.read("DRV_ID_REVISION_NUMBER_COCO", subnode=0)
        except ILError:
            logger.error(
                f"The revision number cannot be read from the drive with IP: {ip_address}."
            )
            revision_number = None
        if not isinstance(revision_number, int):
            raise TypeError(f"Expected revision number type to be int, got {type(revision_number)}")
        self.disconnect_from_slave(servo)
        return SlaveInfo(product_code, revision_number)

    def _remove_servo(self, servo: Servo) -> None:
        """Remove a disconnected servo from the network."""
        self.servos.remove(servo)

        if not self.servos:
            self.stop_status_listener()

    @property
    def protocol(self) -> NetProt:
        """Obtain network protocol."""
        return NetProt.ETH


class EthernetNetwork(EthernetNetworkBase[EthernetServo]):
    """Network for all Ethernet communications.

    Args:
        subnet: The subnet in CIDR notation.
        interface: The network interface used for IPv6 communication.

    """

    def __init__(
        self,
        subnet: Optional[str] = None,
        interface: Optional[str] = None,
    ) -> None:
        super().__init__(subnet=subnet)
        self.__interface = interface
        self._sdcp_nodes: OrderedDict[NodeIdentity, SDCPNode] = OrderedDict()

    def scan_sdcp_nodes(
        self,
        timeout: float = DEFAULT_SDCP_TIMEOUT_S,
    ) -> list[SDCPNode]:
        """Discover SDCP-compatible nodes through IPv6.

        IPv6 devices that do not respond to SDCP identification are ignored.
        Previously known nodes are updated instead of replaced, preserving
        their identity across endpoint, firmware, and mode changes.

        Args:
            timeout: Timeout in seconds for SDCP identification transactions.

        Returns:
            SDCP nodes identified during the current scan.

        Raises:
            ValueError: If no network interface was configured.
        """
        if self.__interface is None:
            raise ValueError("A network interface is required to scan SDCP nodes")

        discovered_nodes: OrderedDict[NodeIdentity, SDCPNode] = OrderedDict()
        for target in discover_ipv6_devices(self.__interface):
            try:
                discovery = identify_sdcp_node(
                    target=target,
                    interface=self.__interface,
                    timeout=timeout,
                )
            except ILError:
                continue

            identity: NodeIdentity = (
                discovery.product_code,
                discovery.serial_number,
            )
            node = self._sdcp_nodes.get(identity)
            if node is None:
                node = SDCPNode(discovery)
                self._sdcp_nodes[identity] = node
            else:
                node.update(discovery)
            discovered_nodes[identity] = node

        return list(discovered_nodes.values())

    def connect_to_node(
        self,
        node: SDCPNode,
        dictionary: str,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
        connection_timeout: float = DEFAULT_SDCP_TIMEOUT_S,
    ) -> SDCPServo:
        """Connect to an SDCP node managed by the network.

        Args:
            node: SDCP node to connect to.
            dictionary: Path to the target dictionary file.
            servo_status_listener: Whether to start the servo status listener.
            net_status_listener: Whether to start the network status listener.
            disconnect_callback: Callback invoked when the servo is disconnected.
            connection_timeout: Timeout in seconds for SDCP transactions.

        Returns:
            Connected SDCP servo.

        Raises:
            ValueError: If the node is not managed by this network.
        """
        self._validate_sdcp_node(node)

        servo = node.connect(
            dictionary_path=dictionary,
            servo_status_listener=servo_status_listener,
            disconnect_callback=disconnect_callback,
            connection_timeout=connection_timeout,
        )
        self.servos.append(servo)
        self._set_servo_state(servo, NetState.CONNECTED)

        if net_status_listener:
            self.start_status_listener()

        return servo

    def disconnect_from_node(self, node: SDCPNode) -> None:
        """Disconnect from an SDCP node managed by the network.

        Args:
            node: SDCP node to disconnect from.

        Raises:
            ValueError: If the node is not managed by the network or is not
                connected through it.
        """
        self._validate_sdcp_node(node)

        servo = node.servo
        if servo is None or servo not in self.servos:
            raise ValueError("The SDCP node is not connected through this network")

        servo.stop_status_listener()
        node.disconnect()
        self._set_servo_state(servo, NetState.DISCONNECTED)
        self._remove_servo(servo)

    def _validate_sdcp_node(self, node: SDCPNode) -> None:
        """Validate that an SDCP node is managed by this network.

        Args:
            node: SDCP node to validate.

        Raises:
            ValueError: If the node is not managed by this network.
        """
        if self._sdcp_nodes.get(node.identity) is not node:
            raise ValueError("The SDCP node is not managed by this network")

    @property
    def sdcp_nodes(self) -> list[SDCPNode]:
        """The list of SDCP nodes managed by the network.

        Returns:
            Copy of the list of SDCP nodes managed by the network.
        """
        return list(self._sdcp_nodes.values())

    @property
    def interface(self) -> Optional[str]:
        """Interface used for IPv6 communication."""
        return self.__interface

    def _create_servo(
        self,
        *,
        target: str,
        dictionary: str,
        port: int,
        connection_timeout: float,
        servo_status_listener: bool,
        is_eoe: bool,
        disconnect_callback: Optional[Callable[[Servo], None]],
    ) -> EthernetServo:
        return EthernetServo(
            target,
            dictionary,
            port,
            connection_timeout,
            servo_status_listener,
            is_eoe,
            disconnect_callback=disconnect_callback,
        )
