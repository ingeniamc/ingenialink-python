import socket

VIRTUAL_DRIVE_IP_ADDRESS = "127.0.0.1"


class VirtualNetworkBase:
    """Base class for shared virtual network behavior."""

    def __init__(self) -> None:
        self.virtual_drive_ip_address = VIRTUAL_DRIVE_IP_ADDRESS

    def create_connection(self, connection_timeout: float, port: int) -> socket.socket:
        """Creates a socket connection to the virtual drive.

        Args:
            connection_timeout: Time in seconds of the connection timeout.
            port: Port to connect to the slave.

        Returns:
            Socket connected to the virtual drive.

        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(connection_timeout)
        sock.connect((self.virtual_drive_ip_address, port))
        return sock
