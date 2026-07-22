"""Upload LFU firmware files through TFTP over IPv6."""

import socket
import struct
import sys
import time
from pathlib import Path
from typing import Optional, Union

import ingenialogger

from ingenialink.exceptions import ILFirmwareLoadError
from ingenialink.utils.ipv6_discovery import (
    IPV6_HEADER_SIZE,
    IPV6_NEXT_HEADER_OFFSET,
    IPV6_SOURCE_ADDRESS_OFFSET,
    _get_interface_index,
    _get_ipv6_extension_header,
    _get_ipv6_offset,
)
from ingenialink.utils.ipv6_pcap_capture import PcapCapture

logger = ingenialogger.get_logger(__name__)

TFTP_PORT = 69
TFTP_TRANSFER_PORT = 20_069
TFTP_BLOCK_SIZE = 512
TFTP_MAX_PACKET_SIZE = 65_535
TFTP_WRQ = 2
TFTP_DATA = 3
TFTP_ACK = 4
TFTP_ERROR = 5
TFTP_MODE = b"octet"
TFTP_TIMEOUT_S = 5.0
TFTP_RETRIES = 3
IPV6_NEXT_HEADER_UDP = 17
UDP_HEADER_SIZE = 8

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
                if sys.platform == "win32":
                    # Windows receives the WRQ acknowledgement through packet capture.
                    with PcapCapture(self._interface) as capture:
                        transfer_address = self._send_write_request(
                            tftp_socket, server_address, path.name, capture
                        )
                else:
                    # Other platforms receive the WRQ acknowledgement from the UDP socket.
                    transfer_address = self._send_write_request(
                        tftp_socket, server_address, path.name
                    )
                self._upload_blocks(tftp_socket, transfer_address, path)
        except OSError as exc:
            raise ILFirmwareLoadError("Unable to upload firmware through IPv6 TFTP.") from exc

        logger.info("IPv6 TFTP firmware upload completed successfully.")

    @staticmethod
    def _send_write_request(
        tftp_socket: socket.socket,
        server_address: IPv6SocketAddress,
        filename: str,
        capture: Optional[PcapCapture] = None,
    ) -> IPv6SocketAddress:
        """Send a WRQ and wait for ACK 0 before returning the transfer address.

        On Windows, ``capture`` is provided and is used to receive ACK 0. On
        other platforms, ACK 0 is received directly from ``tftp_socket``.

        Args:
            tftp_socket: UDP socket used to send the WRQ and, outside Windows,
                receive ACK 0.
            server_address: IPv6 address of the server's TFTP endpoint.
            filename: Name of the firmware file to upload.
            capture: Windows packet capture used to receive ACK 0.

        Returns:
            IPv6 address of the server transfer endpoint.

        Raises:
            ILFirmwareLoadError: If TFTP ACK 0 is not received.
        """
        write_request = TftpUploader._create_write_request(filename)
        tftp_socket.sendto(write_request, server_address)
        host, _, flowinfo, scopeid = server_address
        transfer_address = (host, TFTP_TRANSFER_PORT, flowinfo, scopeid)
        if capture is not None:
            local_port = tftp_socket.getsockname()[1]
            deadline = time.monotonic() + TFTP_TIMEOUT_S
            while time.monotonic() < deadline:
                packet = capture.read_packet()
                if packet is not None and TftpUploader._is_tftp_acknowledgement(
                    packet, host, local_port
                ):
                    return transfer_address
            raise ILFirmwareLoadError("No TFTP ACK received for block 0.")

        try:
            while True:
                response, sender_address = tftp_socket.recvfrom(TFTP_MAX_PACKET_SIZE)
                if sender_address != transfer_address:
                    continue
                TftpUploader._raise_if_tftp_error(response)
                if TftpUploader._get_acknowledged_block(response) == 0:
                    return transfer_address
        except socket.timeout as exc:
            raise ILFirmwareLoadError("No TFTP ACK received for block 0.") from exc

    @staticmethod
    def _upload_blocks(
        tftp_socket: socket.socket,
        transfer_address: IPv6SocketAddress,
        firmware_file: Path,
    ) -> None:
        """Send sequential TFTP data blocks until the final block is acknowledged."""
        block_number = 1
        with firmware_file.open("rb") as file:
            while True:
                data = file.read(TFTP_BLOCK_SIZE)
                packet = struct.pack("!HH", TFTP_DATA, block_number) + data
                TftpUploader._send_data_block(tftp_socket, transfer_address, packet, block_number)
                if len(data) < TFTP_BLOCK_SIZE:
                    return
                block_number = (block_number + 1) & 0xFFFF

    @staticmethod
    def _send_data_block(
        tftp_socket: socket.socket,
        transfer_address: IPv6SocketAddress,
        packet: bytes,
        block_number: int,
    ) -> None:
        """Send one DATA packet and wait for its matching ACK.

        Raises:
            ILFirmwareLoadError: If the server rejects or does not acknowledge the data.
        """
        previous_block = (block_number - 1) & 0xFFFF
        for _ in range(TFTP_RETRIES + 1):
            tftp_socket.sendto(packet, transfer_address)
            try:
                while True:
                    response, sender_address = tftp_socket.recvfrom(TFTP_MAX_PACKET_SIZE)
                    if sender_address != transfer_address:
                        continue
                    TftpUploader._raise_if_tftp_error(response)
                    acknowledged_block = TftpUploader._get_acknowledged_block(response)
                    if acknowledged_block == block_number:
                        return
                    if acknowledged_block == previous_block:
                        break
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
    def _is_tftp_acknowledgement(packet: bytes, drive_address: str, local_port: int) -> bool:
        """Return whether a Windows-captured Ethernet frame contains TFTP ACK 0.

        The packet-capture path uses this helper to validate an IPv6 UDP frame
        from the drive's TFTP transfer port to the local UDP socket.
        """
        ipv6_offset = _get_ipv6_offset(packet)
        if ipv6_offset is None or len(packet) < ipv6_offset + IPV6_HEADER_SIZE:
            return False
        if packet[ipv6_offset] >> 4 != 6:
            return False
        next_header = packet[ipv6_offset + IPV6_NEXT_HEADER_OFFSET]
        udp_offset = ipv6_offset + IPV6_HEADER_SIZE
        while next_header != IPV6_NEXT_HEADER_UDP:
            extension_header = _get_ipv6_extension_header(packet, udp_offset, next_header)
            if extension_header is None:
                return False
            next_header, udp_offset = extension_header
        if len(packet) < udp_offset + UDP_HEADER_SIZE:
            return False
        source_address = packet[
            ipv6_offset + IPV6_SOURCE_ADDRESS_OFFSET : ipv6_offset + IPV6_SOURCE_ADDRESS_OFFSET + 16
        ]
        source_port = int.from_bytes(packet[udp_offset : udp_offset + 2], "big")
        destination_port = int.from_bytes(packet[udp_offset + 2 : udp_offset + 4], "big")
        return (
            source_address == socket.inet_pton(socket.AF_INET6, drive_address)
            and source_port == TFTP_TRANSFER_PORT
            and destination_port == local_port
            and TftpUploader._get_acknowledged_block(packet[udp_offset + UDP_HEADER_SIZE :]) == 0
        )

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
