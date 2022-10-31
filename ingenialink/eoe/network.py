import socket
from enum import Enum

from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.constants import DEFAULT_ETH_CONNECTION_TIMEOUT


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

    """
    def __init__(self, ifname):
        super(EoENetwork, self).__init__()
        self.ifname = ifname
        self._eoe_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._initialize_eoe_service()

    def start_eoe_service(self):
        """Starts the EoE service"""
        pass

    def connect_to_slave(self, target, dictionary=None, port=1061,
                         connection_timeout=DEFAULT_ETH_CONNECTION_TIMEOUT,
                         servo_status_listener=False,
                         net_status_listener=False):
        pass

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

        """
        self._eoe_socket.send(msg)
        resp = self._eoe_socket.recv(1024)
        return int.from_bytes(resp, "big")

    def _connect_to_eoe_service(self):
        """Connect to the EoE service."""
        self._eoe_socket.connect(("127.0.0.1", 8888))

    def _initialize_eoe_service(self):
        """Initialize the virtual network interface and
        the packet forwarder."""
        self._connect_to_eoe_service()
        msg = self._build_eoe_command_msg(EoECommand.INIT.value)
        r = self._send_command(msg)
        if r < 0:
            raise ValueError("Failed to initialize EoE service")

    def _configure_slave(self, node, ip_address):
        """
        Configure an EtherCAT slave with a given IP.

        Args:
            node (int): Targeted node ID.
            ip_address (str): IP address to be set to the slave.

        """
        pass





