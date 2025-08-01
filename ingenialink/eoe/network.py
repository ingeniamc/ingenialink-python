import contextlib
import ipaddress
import socket
import time
from collections import OrderedDict
from enum import Enum
from threading import Thread
from typing import Callable, Optional

import ingenialogger
from typing_extensions import override

from ingenialink import constants
from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.ethernet.servo import EthernetServo
from ingenialink.exceptions import ILError, ILIOError, ILTimeoutError
from ingenialink.network import NetDevEvt, SlaveInfo
from ingenialink.servo import Servo

logger = ingenialogger.get_logger(__name__)


class EoECommand(Enum):
    """EoE command enum."""

    INIT = 0
    DEINIT = 1
    SCAN = 2
    CONFIG = 3
    ERASE_CONFIG = 4
    EOE_START = 5
    EOE_STOP = 6
    GET_STATUS = 7


class EoENetwork(EthernetNetwork):
    """Network for EoE (Ethernet over EtherCAT) communication.

    Args:
        ifname: Network interface name.
        connection_timeout: Time in seconds of the connection timeout to the EoE service.

    """

    EOE_MSG_CMD_SIZE = 2
    EOE_MSG_NODE_SIZE = 2
    EOE_MSG_IP_SIZE = 4
    EOE_MSG_DATA_SIZE = 53
    EOE_MSG_FRAME_SIZE = EOE_MSG_CMD_SIZE + EOE_MSG_DATA_SIZE
    NULL_TERMINATOR = b"\x00"

    STATUS_EOE_BIT = 0b10
    STATUS_INIT_BIT = 0b1
    WAIT_EOE_TIMEOUT = 1

    ECAT_SERVICE_NETWORK = ipaddress.ip_network("192.168.3.0/24")

    # The timeout used by the EoE Service is 4 times the EC_TIMEOUTSTATE
    # https://github.com/OpenEtherCATsociety/SOEM/blob/v1.4.0/soem/ethercattype.h#L76
    # An extra second is added to compensate for the communication delays.
    EOE_SERVICE_STATE_CHANGE_TIMEOUT = 9.0

    def __init__(
        self, ifname: str, connection_timeout: float = constants.DEFAULT_ETH_CONNECTION_TIMEOUT
    ) -> None:
        super().__init__()
        self.ifname = ifname
        self.__connection_timeout = connection_timeout
        self._eoe_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._eoe_socket.settimeout(self.__connection_timeout)
        self._connect_to_eoe_service()
        status = self._get_status_eoe_service()
        if status & self.STATUS_EOE_BIT:
            self._stop_eoe_service()
            self._erase_config_eoe_service()
        if status & self.STATUS_INIT_BIT:
            self._deinitialize_eoe_service()
        self._eoe_service_init = False
        self._eoe_service_started = False
        self._configured_slaves: dict[str, int] = {}

    def connect_to_slave(  # type: ignore [override]
        self,
        slave_id: int,
        ip_address: str,
        dictionary: str,
        port: int = 1061,
        connection_timeout: float = constants.DEFAULT_ETH_CONNECTION_TIMEOUT,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ) -> EthernetServo:
        """Connects to a slave through the given network settings.

        Args:
            slave_id: EtherCAT slave ID.
            ip_address: IP address to be assigned to the slave.
            dictionary: Path to the target dictionary file.
            port: Port to connect to the slave.
            connection_timeout: Time in seconds of the connection timeout.
            servo_status_listener: Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener: Toggle the listener of the network
                status, connection and disconnection.
            disconnect_callback: Callback function to be called when the servo is disconnected.
                If not specified, no callback will be called.

        Raises:
            ValueError: ip_address must be a subnetwork of 192.168.3.0/24.

        Returns:
            EthernetServo: Instance of the servo connected.
        """
        if ipaddress.ip_address(ip_address) not in self.ECAT_SERVICE_NETWORK:
            raise ValueError("ip_address must be a subnetwork of 192.168.3.0/24")
        if not self._eoe_service_init:
            self._initialize_eoe_service()
        if self._eoe_service_started:
            self._stop_eoe_service()
            self._erase_config_eoe_service()
        self.__reconfigure_drives()
        try:
            self._configure_slave(slave_id, ip_address)
        finally:
            self._start_eoe_service()
        self.__wait_eoe_starts()
        self._configured_slaves[ip_address] = slave_id
        self.subscribe_to_status(ip_address, self._recover_from_power_cycle)
        return super().connect_to_slave(
            target=ip_address,
            dictionary=dictionary,
            port=port,
            connection_timeout=connection_timeout,
            servo_status_listener=servo_status_listener,
            net_status_listener=net_status_listener,
            is_eoe=True,
            disconnect_callback=disconnect_callback,
        )

    def __wait_eoe_starts(self) -> None:
        """Wait until the EoE service starts the EoE or the timeout was reached."""
        status = self._get_status_eoe_service()
        time_start = time.time()
        while not status & self.STATUS_EOE_BIT and time.time() - time_start < self.WAIT_EOE_TIMEOUT:
            time.sleep(0.1)
            status = self._get_status_eoe_service()
        if not status & self.STATUS_EOE_BIT:
            logger.warning("Service did not starts the EoE")

    def __reconfigure_drives(self) -> None:
        """Reconfigure all the slaves saved in the network."""
        try:
            for ip_addr, slave_id in self._configured_slaves.items():
                self._configure_slave(slave_id, ip_addr)
        except ILError as e:
            logger.error(e)

    @override
    def disconnect_from_slave(self, servo: EthernetServo) -> None:  # type: ignore [override]
        del self._configured_slaves[servo.ip_address]
        super().disconnect_from_slave(servo)
        if len(self.servos) == 0:
            self._stop_eoe_service()
            self._erase_config_eoe_service()
            try:
                self._deinitialize_eoe_service()
            except ILError as e:
                logger.error(e)

    def __del__(self) -> None:
        """Delete method."""
        self._eoe_socket.shutdown(socket.SHUT_RDWR)
        self._eoe_socket.close()

    def scan_slaves(self) -> list[int]:  # type: ignore [override]
        """Scan slaves connected to the network adapter.

        Returns:
            List containing the ids of the connected slaves.
        """
        deinit_later = False
        if not self._eoe_service_init:
            deinit_later = True
            self._initialize_eoe_service()
        result = self._scan_eoe_service()
        if deinit_later:
            self._deinitialize_eoe_service()
        return result

    def _scan_eoe_service(self) -> list[int]:
        """Make the scan request to the EoE service.

        Returns:
            List containing the ids of the connected slaves.

        Raises:
            ILError: If the EoE service fails to perform a scan.

        """
        msg = self._build_eoe_command_msg(EoECommand.SCAN.value)
        try:
            r = self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ILError(
                "Failed to perform a network scan. Please verify the EoE service is running."
            ) from e
        return list(range(1, r + 1))

    @override
    def scan_slaves_info(self) -> OrderedDict[int, SlaveInfo]:  # type: ignore [override]
        raise NotImplementedError

    @staticmethod
    def _build_eoe_command_msg(cmd: int, data: Optional[bytes] = None) -> bytes:
        """Build a message with the following format.

        +----------+----------+
        |   cmd    |   data   |
        +==========+==========+
        |  2 Byte  | 53 Bytes |
        +----------+----------+

        Args:
            cmd: Indicates which operation to perform.
            data: Contains the necessary data to perform the desired command.

        Returns:
            The message to send.

        """
        if data is None:
            data = b""
        cmd_field = cmd.to_bytes(EoENetwork.EOE_MSG_CMD_SIZE, "little")
        data_field = data + EoENetwork.NULL_TERMINATOR * (EoENetwork.EOE_MSG_DATA_SIZE - len(data))
        return cmd_field + data_field

    def _send_command(self, msg: bytes) -> int:
        """Send command to EoE service.

        Args:
            msg: Message to send.

        Returns:
            Response from the EoE service.

        Raises:
            ILTimeoutError: Timeout while receiving a response from
            the EoE service.
            ILIOError: Error while sending/receiving message.

        """
        try:
            self._eoe_socket.send(msg)
        except OSError as e:
            raise ILIOError("Error sending message.") from e
        try:
            response = self._eoe_socket.recv(1024)
        except socket.timeout as e:
            raise ILTimeoutError("Timeout while receiving response.") from e
        except OSError as e:
            raise ILIOError("Error receiving response.") from e
        return int.from_bytes(response, byteorder="little", signed=True)

    def _connect_to_eoe_service(self) -> None:
        """Connect to the EoE service."""
        self._eoe_socket.connect(("127.0.0.1", 8888))

    def _initialize_eoe_service(self) -> None:
        """Initialize the virtual network interface and the packet forwarder.

        Raises:
            ILError: If the EoE service is not running.
            ILError: If the EoE service cannot be started on the network interface.

        """
        self._eoe_service_init = True
        data = self.ifname
        msg = self._build_eoe_command_msg(EoECommand.INIT.value, data=data.encode("utf-8"))
        self._eoe_socket.settimeout(
            max(self.EOE_SERVICE_STATE_CHANGE_TIMEOUT, self.__connection_timeout)
        )
        try:
            r = self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ILError(
                "Failed to initialize the EoE service. Please verify it's running."
            ) from e
        if r < 0:
            raise ILError(f"Failed to initialize the EoE service using interface {self.ifname}.")
        self._eoe_socket.settimeout(self.__connection_timeout)

    def _deinitialize_eoe_service(self) -> None:
        """Deinitialize the virtual network interface and the packet forwarder.

        Raises:
            ILError: If the EoE service is not running.
            ILError: If the EoE service cannot be stopped on the network interface.

        """
        data = self.ifname
        msg = self._build_eoe_command_msg(EoECommand.DEINIT.value, data=data.encode("utf-8"))
        try:
            self._send_command(msg)
            self._eoe_service_init = False
        except (ILIOError, ILTimeoutError) as e:
            raise ILError("Failed to deinitialize the EoE service.") from e

    def _configure_slave(
        self, slave_id: int, ip_address: str, net_mask: str = "255.255.255.0"
    ) -> None:
        """Configure an EtherCAT slave with a given IP.

        Args:
            slave_id: EtherCAT slave ID.
            ip_address: IP address to be set to the slave.
            net_mask: The subnet mask.

        Raises:
            ILError: If the EoE service fails to configure a slave.

        """
        slave_bytes = slave_id.to_bytes(self.EOE_MSG_NODE_SIZE, "little")
        ip_int = int(ipaddress.IPv4Address(ip_address))
        ip_bytes = ip_int.to_bytes(self.EOE_MSG_IP_SIZE, "little")
        net_mask_int = int(ipaddress.IPv4Address(net_mask))
        net_mask_bytes = net_mask_int.to_bytes(self.EOE_MSG_IP_SIZE, "little")
        data = slave_bytes + ip_bytes + net_mask_bytes
        msg = self._build_eoe_command_msg(EoECommand.CONFIG.value, data)
        try:
            self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ILError(f"Failed to configure slave {slave_id} with IP {ip_address}.") from e

    def _start_eoe_service(self) -> None:
        """Starts the EoE service.

        Raises:
           ILError: If the EoE service fails to start.

        """
        self._eoe_service_started = True
        msg = self._build_eoe_command_msg(EoECommand.EOE_START.value)
        try:
            self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ILError("Failed to start the EoE service.") from e

    def _stop_eoe_service(self) -> None:
        """Stops the EoE service.

        Raises:
           ILError: If the EoE service fails to stop.

        """
        self._eoe_service_started = False
        msg = self._build_eoe_command_msg(EoECommand.EOE_STOP.value)
        try:
            self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ILError("Failed to stop the EoE service.") from e

    def _erase_config_eoe_service(self) -> None:
        """Stops the EoE service.

        Raises:
           ILError: If the EoE service fails to stop.

        """
        msg = self._build_eoe_command_msg(EoECommand.ERASE_CONFIG.value)
        try:
            self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ILError("Failed to stop the EoE service.") from e

    def _get_status_eoe_service(self) -> int:
        """Get the EoE service status.

        +-----------+------+------+
        |ECAT status| init | eoe  |
        +===========+======+======+
        |   1Byte   | 1bit | 1bit |
        +-----------+------+------+

        Returns:
            Status response

        Raises:
           ILError: If get status request fails.

        """
        msg = self._build_eoe_command_msg(EoECommand.GET_STATUS.value)
        try:
            r = self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ILError("Failed to get service status.") from e
        return r

    @override
    def load_firmware_moco(self) -> None:  # type: ignore [override]
        raise NotImplementedError

    @override
    def load_firmware(self) -> None:  # type: ignore [override]
        raise NotImplementedError

    def _recover_from_power_cycle(self, status: NetDevEvt) -> None:
        """Recover the connection after a power cycle.

        Args:
            status: The network status.

        """
        if status == NetDevEvt.REMOVED:
            connection_recovery_thread = Thread(target=self._connection_recovery)
            connection_recovery_thread.start()

    def _connection_recovery(self) -> None:
        """Restart the EoE service until all slaves are detected."""
        while not all(servo.is_alive() for servo in self.servos):
            with contextlib.suppress(ILError):
                self._stop_eoe_service()
                self._deinitialize_eoe_service()
                self._eoe_service_init = False
                self._initialize_eoe_service()
                self.__reconfigure_drives()
                self._start_eoe_service()
