import contextlib
import ftplib
import ipaddress
import os
import socket
import time
from collections import OrderedDict, defaultdict
from ftplib import FTP
from threading import Thread
from time import sleep
from typing import Any, Callable, Optional, Union

import ingenialogger
from multiping import multi_ping
from typing_extensions import override

from ingenialink.constants import DEFAULT_ETH_CONNECTION_TIMEOUT
from ingenialink.exceptions import ILError, ILFirmwareLoadError
from ingenialink.network import NetDevEvt, NetProt, NetState, Network, SlaveInfo
from ingenialink.servo import Servo
from ingenialink.utils.udp import UDP

from .servo import EthernetServo

logger = ingenialogger.get_logger(__name__)

FTP_SESSION_OK_CODE = "220"
FTP_LOGIN_OK_CODE = "230"
FTP_FILE_TRANSFER_OK_CODE = "226"
FTP_CLOSE_OK_CODE = "221"

CMD_CHANGE_CPU = 0x67E4

MAX_NUM_UNSUCCESSFUL_PINGS = 3

MAX_NUMBER_OF_SCAN_TRIES = 2
SCAN_CONNECTION_TIMEOUT = 0.5

VIRTUAL_DRIVE_DICTIONARY = os.path.join(
    os.path.dirname(__file__), "..", "..", "virtual_drive", "resources", "virtual_drive.xdf"
)


class NetStatusListener(Thread):
    """Network status listener thread to check if the drive is alive.

    Args:
        network: Network instance of the Ethernet communication.

    """

    def __init__(self, network: "EthernetNetwork", refresh_time: float = 0.25) -> None:
        super().__init__()
        self.__network = network
        self.__refresh_time = refresh_time
        self.__stop = False
        self.__max_unsuccessful_pings = MAX_NUM_UNSUCCESSFUL_PINGS

    def run(self) -> None:
        """Check the network status."""
        while not self.__stop:
            for servo in self.__network.servos:
                unsuccessful_pings = 0
                servo_ip = servo.ip_address
                servo_state = self.__network.get_servo_state(servo_ip)
                while unsuccessful_pings < self.__max_unsuccessful_pings:
                    response = servo.is_alive()
                    if not response:
                        unsuccessful_pings += 1
                    else:
                        break
                ping_response = unsuccessful_pings != self.__max_unsuccessful_pings
                if servo_state == NetState.CONNECTED and not ping_response:
                    self.__network._notify_status(servo_ip, NetDevEvt.REMOVED)
                    self.__network._set_servo_state(servo_ip, NetState.DISCONNECTED)
                if servo_state == NetState.DISCONNECTED and ping_response:
                    self.__network._notify_status(servo_ip, NetDevEvt.ADDED)
                    self.__network._set_servo_state(servo_ip, NetState.CONNECTED)
            time.sleep(self.__refresh_time)

    def stop(self) -> None:
        """Stop the listener."""
        self.__stop = True


class EthernetNetwork(Network):
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
        self.__listener_net_status: Optional[NetStatusListener] = None
        self.__observers_net_state: dict[str, list[Callable[[NetDevEvt], Any]]] = defaultdict(list)

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
    ) -> EthernetServo:
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

        Raises:
            ILError: If the drive is not found.

        Returns:
            EthernetServo: Instance of the servo connected.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(connection_timeout)
        sock.connect((target, port))
        servo = EthernetServo(
            sock, dictionary, servo_status_listener, is_eoe, disconnect_callback=disconnect_callback
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
        else:
            self.stop_status_listener()
        return servo

    def disconnect_from_slave(self, servo: EthernetServo) -> None:  # type: ignore [override]
        """Disconnects the slave from the network.

        Args:
            servo: Instance of the servo connected.

        """
        # Notify that disconnect_from_slave has been called
        if servo._disconnect_callback:
            servo._disconnect_callback(servo)
        self.servos.remove(servo)
        servo.stop_status_listener()
        self.close_socket(servo.socket)
        self._set_servo_state(servo.ip_address, NetState.DISCONNECTED)
        if len(self.servos) == 0:
            self.stop_status_listener()

    @staticmethod
    def close_socket(sock: socket.socket) -> None:
        """Closes the established network socket."""
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()

    def start_status_listener(self) -> None:
        """Start monitoring network events (CONNECTION/DISCONNECTION)."""
        if self.__listener_net_status is None:
            listener = NetStatusListener(self)
            listener.start()
            self.__listener_net_status = listener

    def stop_status_listener(self) -> None:
        """Stops the NetStatusListener from listening to the drive."""
        if self.__listener_net_status is not None:
            self.__listener_net_status.stop()
            self.__listener_net_status.join()
        self.__listener_net_status = None

    def _notify_status(self, ip: str, status: NetDevEvt) -> None:
        """Notify subscribers of a network state change."""
        for callback in self.__observers_net_state[ip]:
            callback(status)

    def subscribe_to_status(self, ip: str, callback: Callable[[NetDevEvt], Any]) -> None:  # type: ignore [override]
        """Subscribe to network state changes.

        Args:
            ip: IP of the drive to subscribe.
            callback: Callback function.

        """
        if callback in self.__observers_net_state[ip]:
            logger.info("Callback already subscribed.")
            return
        self.__observers_net_state[ip].append(callback)

    def unsubscribe_from_status(self, ip: str, callback: Callable[[NetDevEvt], Any]) -> None:  # type: ignore [override]
        """Unsubscribe from network state changes.

        Args:
            ip: IP of the drive to unsubscribe.
            callback: Callback function.

        """
        if callback not in self.__observers_net_state[ip]:
            logger.info("Callback not subscribed.")
            return
        self.__observers_net_state[ip].remove(callback)

    def get_servo_state(self, servo_id: Union[int, str]) -> NetState:
        """Get the state of a servo that's a part of network.

        The state indicates if the servo is connected or disconnected.

        Args:
            servo_id: The servo's IP address.

        Raises:
            ValueError: if the servo ID is not a string.

        Returns:
            The servo's state.
        """
        if not isinstance(servo_id, str):
            raise ValueError("The servo ID must be a string.")
        return self._servos_state[servo_id]

    def _set_servo_state(self, servo_id: Union[int, str], state: NetState) -> None:
        """Set the state of a servo that's a part of network.

        Args:
            servo_id: The servo's IP address.
            state: The servo's state.

        """
        self._servos_state[servo_id] = state

    def _get_servo_info_for_scan(self, ip_address: str) -> SlaveInfo:
        """Get the product code and revision number of a drive.

        It's used for the scan_slaves_info method.

        Raises:
            TypeError: if the product code type is not an integer.

        Returns:
            product code and revision number.
        """
        servo = self.connect_to_slave(
            ip_address, VIRTUAL_DRIVE_DICTIONARY, connection_timeout=SCAN_CONNECTION_TIMEOUT
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

    @property
    def protocol(self) -> NetProt:
        """Obtain network protocol."""
        return NetProt.ETH
