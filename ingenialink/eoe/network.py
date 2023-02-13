import ipaddress
import socket
from enum import Enum

from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.constants import DEFAULT_ETH_CONNECTION_TIMEOUT
from ingenialink.exceptions import ILTimeoutError, ILIOError, ILError
from ingenialink.constants import EOE_MSG_DATA_SIZE, EOE_MSG_NODE_SIZE, NULL_TERMINATOR


class EoECommand(Enum):
    INIT = "0"
    SCAN = "1"
    CONFIG = "2"
    START = "3"
    STOP = "4"


class EoENetwork(EthernetNetwork):
    """Network for EoE (Ethernet over EtherCAT) communication.

    Args:
        ifname (str): Network interface name.
        connection_timeout (float): Time in seconds of the connection timeout
        to the EoE service.

    """

    def __init__(self, ifname, connection_timeout=DEFAULT_ETH_CONNECTION_TIMEOUT):
        super().__init__()
        self.ifname = ifname
        self._eoe_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._eoe_socket.settimeout(connection_timeout)
        self._connect_to_eoe_service()
        self._eoe_service_started = False

    def connect_to_slave(
        self,
        slave_id,
        ip_address,
        dictionary=None,
        port=1061,
        connection_timeout=DEFAULT_ETH_CONNECTION_TIMEOUT,
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

        Returns:
            EthernetServo: Instance of the servo connected.

        """
        self._initialize_eoe_service()
        self._configure_slave(slave_id, ip_address)
        self._start_eoe_service()
        return super().connect_to_slave(
            ip_address,
            dictionary,
            port,
            connection_timeout,
            servo_status_listener,
            net_status_listener,
        )

    def disconnect_from_slave(self, servo):
        super().disconnect_from_slave(servo)
        if len(self.servos) == 0:
            self._stop_eoe_service()
            self._eoe_socket.shutdown(socket.SHUT_RDWR)
            self._eoe_socket.close()

    def scan_slaves(self):
        """
        Scan slaves connected to a given network adapter.

        Returns:
            int: Number of detected slaves.

        Raises:
            ILError: If the EoE service fails to perform a scan.

        """
        data = self.ifname
        msg = self._build_eoe_command_msg(EoECommand.SCAN.value, data=data.encode("utf-8"))
        r = self._send_command(msg)
        if r < 0:
            raise ILError(
                f"Failed to initialize the EoE service using interface {self.ifname}."
            )
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
        if data is None:
            data = bytes()
        cmd_field = cmd.encode("utf-8")
        node_field = f"{node:0{EOE_MSG_NODE_SIZE}d}".encode("utf-8")
        data_field = data + NULL_TERMINATOR * (EOE_MSG_DATA_SIZE - len(data))
        return cmd_field + node_field + NULL_TERMINATOR + data_field + NULL_TERMINATOR

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
        return int.from_bytes(response, byteorder="big", signed=True)

    def _connect_to_eoe_service(self):
        """Connect to the EoE service."""
        self._eoe_socket.connect(("127.0.0.1", 8888))

    def _initialize_eoe_service(self):
        """Initialize the virtual network interface and
        the packet forwarder.

        Raises:
            ILError: If the EoE service is not running.
            ILError: If the EoE service cannot be started on the network interface.

        """
        data = self.ifname
        msg = self._build_eoe_command_msg(EoECommand.INIT.value, data=data.encode("utf-8"))
        try:
            r = self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ILError(
                "Failed to initialize the EoE service. Please verify it's running."
            ) from e
        if r < 0:
            raise ILError(
                f"Failed to initialize the EoE service using interface {self.ifname}."
            )

    def _configure_slave(self, slave_id, ip_address):
        """
        Configure an EtherCAT slave with a given IP.

        Args:
            slave_id (int): EtherCAT slave ID.
            ip_address (str): IP address to be set to the slave.

        Raises:
            ILError: If the EoE service fails to configure a slave.

        """
        ip_int = int(ipaddress.IPv4Address(ip_address))
        ip_bytes = bytes(str(ip_int), "utf-8")
        msg = self._build_eoe_command_msg(EoECommand.CONFIG.value, slave_id, ip_bytes)
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
        msg = self._build_eoe_command_msg(EoECommand.START.value)
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
        msg = self._build_eoe_command_msg(EoECommand.STOP.value)
        try:
            self._send_command(msg)
        except (ILIOError, ILTimeoutError) as e:
            raise ILError("Failed to stop the EoE service.") from e
