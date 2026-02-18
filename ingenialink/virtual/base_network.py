import socket

from virtual_drive.core import VirtualDrive


class VirtualNetworkBase:
    """Base class for shared virtual network behavior."""

    def __init__(self) -> None:
        self.virtual_drive_ip_address = VirtualDrive.IP_ADDRESS

    def create_connection(self, connection_timeout: float, port: int) -> socket.socket:
        """Creates a socket connection to the virtual drive.

        Args:
            connection_timeout: Time in seconds of the connection timeout.
            port: Port to connect to the slave.

        Returns:
            socket.socket: Socket connected to the virtual drive.

        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(connection_timeout)
        sock.connect((self.virtual_drive_ip_address, port))
        return sock
