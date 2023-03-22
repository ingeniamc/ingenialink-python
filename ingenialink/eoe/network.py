import ipaddress
import socket
from enum import Enum

import ingenialogger

from ingenialink import constants
from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.exceptions import ILTimeoutError, ILIOError, ILError

logger = ingenialogger.get_logger(__name__)


class EoECommand(Enum):
    INIT = 0
    DEINIT = 1
    SCAN = 2
    CONFIG = 3
    ERASE_CONFIG = 4
    EOE_START = 5
    EOE_STOP = 6


class EoENetwork(EthernetNetwork):
    """Network for EoE (Ethernet over EtherCAT) communication.

    Args:
        ifname (str): Network interface name.
        connection_timeout (float): Time in seconds of the connection timeout
        to the EoE service.

    """

    ECAT_SERVICE_NETWORK = ipaddress.ip_network("192.168.3.0/24")

    def __init__(self, ifname, connection_timeout=constants.DEFAULT_ETH_CONNECTION_TIMEOUT):
        super().__init__()
        self.ifname = ifname
        self._eoe_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._eoe_socket.settimeout(connection_timeout)
        self._connect_to_eoe_service()
        self._eoe_service_started = False
        self._eoe_service_init = False
        self._configured_slaves = {}

    def connect_to_slave(
        self,
        slave_id,
        ip_address,
        dictionary=None,
        port=1061,
        connection_timeout=constants.DEFAULT_ETH_CONNECTION_TIMEOUT,
        servo_status_listener=False,
        net_status_listener=False,
    ):
        """Connects to a slave through the given network settings.

        Args:
            slave_id (int): EtherCAT slave ID.
            ip_address (str): IP address to be assigned to the slave.
            dictionary (str): Path to the target dictionary file.
            port (int): Port to connect to the slave.
            connection_timeout (float): Time in seconds of the connection timeout.
            servo_status_listener (bool): Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener (bool): Toggle the listener of the network
                status, connection and disconnection.

        Raises:
            ValueError: ip_address must be a subnetwork of 192.168.3.0/24
            ILError: If the EoE service is not running.
            ILError: If the EoE service cannot be started on the network interface.

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
        self._configured_slaves[ip_address] = slave_id
        return super().connect_to_slave(
            ip_address,
            dictionary,
            port,
            connection_timeout,
            servo_status_listener,
            net_status_listener,
        )

    def __reconfigure_drives(self):
        for ip_addr, slave_id in self._configured_slaves:
            try:
                self._configure_slave(slave_id, ip_addr)
            except ILError as e:
                logger.error(e)

    def disconnect_from_slave(self, servo):
        del self._configured_slaves[servo.ip_address]
        super().disconnect_from_slave(servo)
        if len(self.servos) == 0:
            self._stop_eoe_service()
            self._erase_config_eoe_service()
            self._deinitialize_eoe_service()
            self._eoe_socket.shutdown(socket.SHUT_RDWR)
            self._eoe_socket.close()

    def scan_slaves(self):
        """
        Scan slaves connected to a given network adapter. If some slaves were connected, the connections will be lost

        Returns:
            list: List containing the ids of the connected slaves.

        Raises:
            ILError: If the EoE service fails to perform a scan.

        """
        deinit_later = False
        was_eoe_started = False
        if self._eoe_service_started:
            was_eoe_started = True
            self._stop_eoe_service()
            self._erase_config_eoe_service()
        if not self._eoe_service_init:
            deinit_later = True
            self._initialize_eoe_service()
        result = self._scan_eoe_service()
        if was_eoe_started:
            self.__reconfigure_drives()
            self._start_eoe_service()
        if deinit_later:
            self._deinitialize_eoe_service()
        return result

    def _scan_eoe_service(self):
        data = self.ifname
        msg = self._build_eoe_command_msg(EoECommand.SCAN.value, data=data.encode("utf-8"))
        try:
            r = self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ILError(
                "Failed to perform a network scan. Please verify the EoE service is running."
            ) from e
        if r < 0:
            raise ILError(f"Failed to initialize the EoE service using interface {self.ifname}.")
        return list(range(1, r + 1))

    @staticmethod
    def _build_eoe_command_msg(cmd, data=None):
        """
        Build a message with the following format.

        +----------+----------+
        |    cmd   |   datac  |
        +==========+==========+
        |  2 Byte  | 53 Bytes |
        +----------+----------+

        Args:
            cmd (int): Indicates which operation to perform.
            data (bytes): Contains the necessary data to perform the desired command.

        Returns:
            bytes: The message to send.

        """
        if data is None:
            data = bytes()
        cmd_field = cmd.to_bytes(constants.EOE_MSG_CMD_SIZE, "little")
        data_field = data + constants.NULL_TERMINATOR * (constants.EOE_MSG_DATA_SIZE - len(data))
        return cmd_field + data_field

    def _send_command(self, msg):
        """
        Send command to EoE service.

        Args:
            msg (bytes): Message to send.

        Returns:
            int: Response from the EoE service.

        Raises:
            ILTimeoutError: Timeout while receiving a response from
            the EoE service.
            ILIOError: Error while sending/receiving message.

        """
        try:
            self._eoe_socket.send(msg)
        except socket.error as e:
            raise ILIOError("Error sending message.") from e
        try:
            response = self._eoe_socket.recv(1024)
        except socket.timeout as e:
            raise ILTimeoutError("Timeout while receiving response.") from e
        except socket.error as e:
            raise ILIOError("Error receiving response.") from e
        return int.from_bytes(response, byteorder="little", signed=True)

    def _connect_to_eoe_service(self):
        """Connect to the EoE service."""
        self._eoe_socket.connect(("127.0.0.1", 8888))

    def _initialize_eoe_service(self):
        """Initialize the virtual network interface and the packet forwarder.

        Raises:
            ILError: If the EoE service is not running.
            ILError: If the EoE service cannot be started on the network interface.

        """
        self._eoe_service_init = True
        data = self.ifname
        msg = self._build_eoe_command_msg(EoECommand.INIT.value, data=data.encode("utf-8"))
        try:
            r = self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ILError(
                "Failed to initialize the EoE service. Please verify it's running."
            ) from e
        if r < 0:
            raise ILError(f"Failed to initialize the EoE service using interface {self.ifname}.")

    def _deinitialize_eoe_service(self):
        """Deinitialize the virtual network interface and the packet forwarder.

        Raises:
            ILError: If the EoE service is not running.
            ILError: If the EoE service cannot be stopped on the network interface.

        """
        self._eoe_service_init = False
        data = self.ifname
        msg = self._build_eoe_command_msg(EoECommand.DEINIT.value, data=data.encode("utf-8"))
        try:
            self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ILError("Failed to deinitialize the EoE service.") from e

    def _configure_slave(self, slave_id, ip_address, net_mask="255.255.255.0"):
        """
        Configure an EtherCAT slave with a given IP.

        Args:
            slave_id (int): EtherCAT slave ID.
            ip_address (str): IP address to be set to the slave.

        Raises:
            ILError: If the EoE service fails to configure a slave.

        """
        slave_bytes = slave_id.to_bytes(constants.EOE_MSG_NODE_SIZE, "little")
        ip_int = int(ipaddress.IPv4Address(ip_address))
        ip_bytes = ip_int.to_bytes(constants.EOE_MSG_IP_SIZE, "little")
        net_mask_int = int(ipaddress.IPv4Address(net_mask))
        net_mask_bytes = net_mask_int.to_bytes(constants.EOE_MSG_IP_SIZE, "little")
        data = slave_bytes + ip_bytes + net_mask_bytes
        msg = self._build_eoe_command_msg(EoECommand.CONFIG.value, data)
        try:
            self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ILError(f"Failed to configure slave {slave_id} with IP {ip_address}.") from e

    def _start_eoe_service(self):
        """Starts the EoE service

        Raises:
           ILError: If the EoE service fails to start.

        """
        self._eoe_service_started = True
        msg = self._build_eoe_command_msg(EoECommand.EOE_START.value)
        try:
            self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ILError("Failed to start the EoE service.") from e

    def _stop_eoe_service(self):
        """Stops the EoE service

        Raises:
           ILError: If the EoE service fails to stop.

        """
        self._eoe_service_started = False
        msg = self._build_eoe_command_msg(EoECommand.EOE_STOP.value)
        try:
            self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ILError("Failed to stop the EoE service.") from e

    def _erase_config_eoe_service(self):
        """Stops the EoE service

        Raises:
           ILError: If the EoE service fails to stop.

        """
        msg = self._build_eoe_command_msg(EoECommand.ERASE_CONFIG.value)
        try:
            self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ILError("Failed to stop the EoE service.") from e
