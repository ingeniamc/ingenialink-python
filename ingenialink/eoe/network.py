import ipaddress
import socket
from enum import Enum

from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.constants import DEFAULT_ETH_CONNECTION_TIMEOUT
from ingenialink.exceptions import ILTimeoutError, ILIOError


class EoECommand(Enum):
    INIT = '0'
    SCAN = '1'
    CONFIG = '2'
    START = '3'
    STOP = '4'


class EoENetwork(EthernetNetwork):
    """Network for EoE (Ethernet over EtherCAT) communication.

        Args:
        ifname (str): Network interface name.
        connection_timeout (float): Time in seconds of the connection timeout
        to the EoE service.

    """
    def __init__(self, ifname,
                 connection_timeout=DEFAULT_ETH_CONNECTION_TIMEOUT):
        super().__init__()
        self.ifname = ifname
        self._eoe_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._eoe_socket.settimeout(connection_timeout)
        self._initialize_eoe_service()
        self._eoe_service_started = False

    def connect_to_slave(self, target, dictionary=None, port=1061,
                         connection_timeout=DEFAULT_ETH_CONNECTION_TIMEOUT,
                         servo_status_listener=False,
                         net_status_listener=False):
        self._configure_slave(target)
        servo = super().connect_to_slave(target,
                                         dictionary, port,
                                         connection_timeout,
                                         servo_status_listener,
                                         net_status_listener)
        if not self._eoe_service_started:
            self._start_eoe_service()
        return servo

    def disconnect_from_slave(self, servo):
        super().disconnect_from_slave(servo)
        if len(self.servos) == 0:
            self._eoe_socket.shutdown(socket.SHUT_RDWR)
            self._eoe_socket.close()

    def scan_slaves(self):
        """
        Scan slaves connected to a given network adapter.

        Returns:
            int: Number of detected slaves.

        """
        data = self.ifname + "\0"
        msg = self._build_eoe_command_msg(EoECommand.SCAN.value,
                                          data=data.encode("utf-8"))
        r = self._send_command(msg)
        if r < 0:
            raise ValueError("Failed to scan slaves")
        return r

    @staticmethod
    def _build_eoe_command_msg(cmd, node=1, data=None):
        """
        Build a message with the following format.

        +----------+----------+----------+
        |    cmd   |   node    |   data  |
        +==========+==========+==========+
        |  1 Byte  |  2 Bytes | 50 Bytes |
        +----------+----------+----------+

        Args:
            cmd (str): Indicates which operation to perform.
            node (int):  Indicates the EtherCAT node ID the command corresponds to.
            data (bytes): Contains the necessary data to perform the desired command.

        Returns:
            bytes: The message to send.

        """
        data = b'\x00' * 50 if data is None else data + b'\x00' * (50 - len(data))
        return cmd.encode('utf-8') + node.to_bytes(2, 'big') + data

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
            raise ILIOError('Error sending message.') from e
        try:
            response = self._eoe_socket.recv(1024)
        except socket.timeout as e:
            raise ILTimeoutError('Timeout while receiving response.') from e
        except socket.error as e:
            raise ILIOError('Error receiving response.') from e
        return int.from_bytes(response, "big")

    def _connect_to_eoe_service(self):
        """Connect to the EoE service."""
        self._eoe_socket.connect(("127.0.0.1", 8888))

    def _initialize_eoe_service(self):
        """Initialize the virtual network interface and
        the packet forwarder."""
        self._connect_to_eoe_service()
        msg = self._build_eoe_command_msg(EoECommand.INIT.value)
        try:
            r = self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ValueError("Failed to initialize the EoE service. "
                             "Please verify it's running.") from e

    def _configure_slave(self, ip_address):
        """
        Configure an EtherCAT slave with a given IP.

        Args:
            ip_address (str): IP address to be set to the slave.

        """
        node = len(self.servos) + 1
        ip_int = int(ipaddress.IPv4Address(ip_address))
        ip_bytes = bytes(str(ip_int), 'utf-8')
        msg = self._build_eoe_command_msg(EoECommand.CONFIG.value, node,
                                          ip_bytes)
        try:
            r = self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ValueError(f"Failed to configure slave {node} with IP "
                             f"{ip_address}.") from e

    def _start_eoe_service(self):
        """Starts the EoE service"""
        self._eoe_service_started = True
        msg = self._build_eoe_command_msg(EoECommand.START.value)
        try:
            r = self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ValueError("Failed to start the EoE service.") from e





