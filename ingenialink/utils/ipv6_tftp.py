"""Upload LFU firmware files through TFTP over IPv6."""

import socket
import struct
from pathlib import Path
from typing import Union

import ingenialogger

from ingenialink.exceptions import ILFirmwareLoadError
from ingenialink.utils.ipv6_discovery import _get_interface_index

logger = ingenialogger.get_logger(__name__)

TFTP_PORT = 69
TFTP_BLOCK_SIZE = 512
TFTP_MAX_PACKET_SIZE = 65_535
TFTP_WRQ = 2
TFTP_DATA = 3
TFTP_ACK = 4
TFTP_ERROR = 5
TFTP_MODE = b"octet"
TFTP_TIMEOUT_S = 5.0
TFTP_RETRIES = 3

IPv6SocketAddress = tuple[str, int, int, int]


class TftpUploader:
    """Upload firmware files to an IPv6 drive through TFTP.

    Args:
        drive_address: IPv6 address of the drive. Link-local addresses are
            scoped with ``interface``.
        interface: Network interface in the same format as
            :func:`ingenialink.utils.ipv6_discovery.discover_ipv6_devices`.
    """

    def __init__(self, drive_address: str, interface: str) -> None:
        self._drive_address = drive_address
        self._interface = interface

    def upload_file(self, firmware_file: Union[str, Path]) -> None:
        """Upload an LFU firmware file through TFTP.

        Args:
            firmware_file: Path to the LFU firmware file.

        Raises:
            FileNotFoundError: If the firmware file does not exist.
            ILFirmwareLoadError: If the file is invalid or the TFTP transfer fails.
        """
        path = Path(firmware_file)
        if not path.is_file():
            raise FileNotFoundError(f"Could not find {path}.")
        if path.suffix.lower() != ".lfu":
            raise ILFirmwareLoadError("The TFTP server only accepts .lfu files.")

        interface_index = _get_interface_index(self._interface)
        server_address = (self._drive_address, TFTP_PORT, 0, interface_index)
        logger.info(f"Uploading firmware to [{self._drive_address}%{interface_index}]:{TFTP_PORT}.")

        try:
            with socket.socket(
                socket.AF_INET6, socket.SOCK_DGRAM, socket.IPPROTO_UDP
            ) as tftp_socket:
                tftp_socket.settimeout(TFTP_TIMEOUT_S)
                transfer_address = self._send_write_request(tftp_socket, server_address, path.name)
                tftp_socket.connect(transfer_address)
                self._upload_blocks(tftp_socket, path)
        except OSError as exc:
            raise ILFirmwareLoadError("Unable to upload firmware through IPv6 TFTP.") from exc

        logger.info("IPv6 TFTP firmware upload completed successfully.")

    @staticmethod
    def _send_write_request(
        tftp_socket: socket.socket,
        server_address: IPv6SocketAddress,
        filename: str,
    ) -> IPv6SocketAddress:
        """Send a WRQ and return the server transfer address after ACK 0.

        Returns:
            IPv6 address of the server transfer endpoint.

        Raises:
            ILFirmwareLoadError: If the server rejects or does not acknowledge the request.
        """
        write_request = TftpUploader._create_write_request(filename)
        for _ in range(TFTP_RETRIES + 1):
            tftp_socket.sendto(write_request, server_address)
            try:
                while True:
                    response, source_address = tftp_socket.recvfrom(TFTP_MAX_PACKET_SIZE)
                    TftpUploader._raise_if_tftp_error(response)
                    if TftpUploader._get_acknowledged_block(response) == 0:
                        return TftpUploader._parse_ipv6_socket_address(source_address)
            except socket.timeout:
                logger.warning("Timeout waiting for TFTP ACK 0; retrying write request.")
        raise ILFirmwareLoadError("No TFTP ACK received for block 0.")

    @staticmethod
    def _upload_blocks(tftp_socket: socket.socket, firmware_file: Path) -> None:
        """Send sequential TFTP data blocks until the final block is acknowledged."""
        block_number = 1
        with firmware_file.open("rb") as file:
            while True:
                data = file.read(TFTP_BLOCK_SIZE)
                packet = struct.pack("!HH", TFTP_DATA, block_number) + data
                TftpUploader._send_data_block(tftp_socket, packet, block_number)
                if len(data) < TFTP_BLOCK_SIZE:
                    return
                block_number = (block_number + 1) & 0xFFFF

    @staticmethod
    def _send_data_block(tftp_socket: socket.socket, packet: bytes, block_number: int) -> None:
        """Send one DATA packet and wait for its matching ACK.

        Raises:
            ILFirmwareLoadError: If the server rejects or does not acknowledge the data.
        """
        previous_block = (block_number - 1) & 0xFFFF
        for _ in range(TFTP_RETRIES + 1):
            tftp_socket.send(packet)
            try:
                while True:
                    response = tftp_socket.recv(TFTP_MAX_PACKET_SIZE)
                    TftpUploader._raise_if_tftp_error(response)
                    acknowledged_block = TftpUploader._get_acknowledged_block(response)
                    if acknowledged_block == block_number:
                        return
                    if acknowledged_block != previous_block:
                        continue
            except socket.timeout:
                logger.warning(f"Timeout waiting for TFTP ACK {block_number}; retrying data block.")
        raise ILFirmwareLoadError(f"No TFTP ACK received for block {block_number}.")

    @staticmethod
    def _create_write_request(filename: str) -> bytes:
        """Create an octet-mode TFTP WRQ packet.

        Returns:
            Encoded TFTP write request.

        Raises:
            ILFirmwareLoadError: If the filename is not ASCII.
        """
        try:
            encoded_filename = filename.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ILFirmwareLoadError(
                "The firmware filename must contain only ASCII characters."
            ) from exc
        return struct.pack("!H", TFTP_WRQ) + encoded_filename + b"\0" + TFTP_MODE + b"\0"

    @staticmethod
    def _get_acknowledged_block(packet: bytes) -> Union[int, None]:
        """Return the acknowledged block when a packet is a valid ACK."""
        if len(packet) < 4 or int.from_bytes(packet[:2], "big") != TFTP_ACK:
            return None
        return int.from_bytes(packet[2:4], "big")

    @staticmethod
    def _raise_if_tftp_error(packet: bytes) -> None:
        """Raise an IngeniaLink error when the server returns TFTP ERROR.

        Raises:
            ILFirmwareLoadError: If the packet is a TFTP error response.
        """
        if len(packet) < 2 or int.from_bytes(packet[:2], "big") != TFTP_ERROR:
            return
        if len(packet) < 4:
            raise ILFirmwareLoadError("The TFTP server returned an invalid error packet.")
        error_code = int.from_bytes(packet[2:4], "big")
        error_message = packet[4:].rstrip(b"\0").decode(errors="replace")
        raise ILFirmwareLoadError(f"TFTP error {error_code}: {error_message}")

    @staticmethod
    def _parse_ipv6_socket_address(address: object) -> IPv6SocketAddress:
        """Validate and return an IPv6 socket address received from the server.

        Returns:
            Validated IPv6 socket address.

        Raises:
            ILFirmwareLoadError: If the address is not a valid IPv6 socket address.
        """
        if (
            not isinstance(address, tuple)
            or len(address) != 4
            or not isinstance(address[0], str)
            or not isinstance(address[1], int)
            or not isinstance(address[2], int)
            or not isinstance(address[3], int)
        ):
            raise ILFirmwareLoadError("The TFTP server returned an invalid transfer address.")
        return address
