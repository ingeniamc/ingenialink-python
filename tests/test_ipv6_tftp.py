import socket
import struct

import pytest

from ingenialink.exceptions import ILFirmwareLoadError
from ingenialink.utils.ipv6_tftp import (
    TFTP_ACK,
    TFTP_DATA,
    TFTP_WRQ,
    TftpUploader,
)


@pytest.fixture
def tftp_socket(mocker):
    """Provide a UDP socket mock that supports the socket context manager.

    Returns:
        Mocked UDP socket.
    """
    socket_mock = mocker.MagicMock()
    socket_mock.__enter__.return_value = socket_mock
    return socket_mock


def _tftp_acknowledgement_frame(source_address: str, destination_port: int) -> bytes:
    """Build an Ethernet-framed IPv6 UDP TFTP ACK 0.

    Returns:
        Ethernet frame containing an IPv6 UDP TFTP ACK 0.
    """
    tftp_acknowledgement = struct.pack("!HH", TFTP_ACK, 0)
    udp_header = struct.pack(
        "!HHHH",
        20_069,
        destination_port,
        8 + len(tftp_acknowledgement),
        0,
    )
    ipv6_header = (
        bytes.fromhex("60000000")
        + struct.pack("!HBB", len(udp_header + tftp_acknowledgement), 17, 64)
        + socket.inet_pton(socket.AF_INET6, source_address)
        + socket.inet_pton(socket.AF_INET6, "fe80::2")
    )
    return bytes(12) + bytes.fromhex("86dd") + ipv6_header + udp_header + tftp_acknowledgement


def test_upload_ipv6_firmware_uses_scoped_address_and_uploads_file(mocker, tftp_socket, tmp_path):
    """Upload a final data block using the discovery interface index."""
    mocker.patch("ingenialink.utils.ipv6_tftp.sys.platform", "linux")
    firmware_file = tmp_path / "firmware.lfu"
    firmware_file.write_bytes(b"firmware")
    interface_index = mocker.patch(
        "ingenialink.utils.ipv6_tftp._get_interface_index", return_value=7
    )
    socket_factory = mocker.patch(
        "ingenialink.utils.ipv6_tftp.socket.socket", return_value=tftp_socket
    )
    tftp_socket.recv.side_effect = [
        struct.pack("!HH", TFTP_ACK, 0),
        struct.pack("!HH", TFTP_ACK, 1),
    ]

    TftpUploader("fe80::1", r"\Device\NPF_{GUID}").upload_file(firmware_file)

    interface_index.assert_called_once_with(r"\Device\NPF_{GUID}")
    socket_factory.assert_called_once_with(socket.AF_INET6, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    tftp_socket.settimeout.assert_called_once_with(5.0)
    write_request, destination = tftp_socket.sendto.call_args_list[0].args
    assert destination == ("fe80::1", 69, 0, 7)
    assert struct.unpack("!H", write_request[:2])[0] == TFTP_WRQ
    tftp_socket.connect.assert_not_called()
    data_packet, transfer_address = tftp_socket.sendto.call_args_list[1].args
    assert transfer_address == ("fe80::1", 20_069, 0, 7)
    assert struct.unpack("!HH", data_packet[:4]) == (TFTP_DATA, 1)
    assert data_packet[4:] == b"firmware"
    assert tftp_socket.sendto.call_count == 2
    tftp_socket.recvfrom.assert_not_called()


def test_upload_ipv6_firmware_rejects_non_lfu_file(tmp_path):
    """Reject files the drive TFTP server cannot accept before using sockets."""
    firmware_file = tmp_path / "firmware.bin"
    firmware_file.touch()

    with pytest.raises(ILFirmwareLoadError, match="only accepts .lfu"):
        TftpUploader("fe80::1", "eth0").upload_file(firmware_file)


def test_upload_ipv6_firmware_retries_data_without_repeating_write_request(
    mocker, tftp_socket, tmp_path
):
    """Retry a data block after its ACK times out without retransmitting the WRQ."""
    mocker.patch("ingenialink.utils.ipv6_tftp.sys.platform", "linux")
    firmware_file = tmp_path / "firmware.lfu"
    firmware_file.write_bytes(b"firmware")
    mocker.patch("ingenialink.utils.ipv6_tftp._get_interface_index", return_value=4)
    mocker.patch("ingenialink.utils.ipv6_tftp.socket.socket", return_value=tftp_socket)
    tftp_socket.recv.side_effect = [
        struct.pack("!HH", TFTP_ACK, 0),
        socket.timeout(),
        struct.pack("!HH", TFTP_ACK, 1),
    ]

    TftpUploader("fe80::1", "eth0").upload_file(firmware_file)

    assert tftp_socket.sendto.call_count == 3
    assert tftp_socket.sendto.call_args_list[0].args[1] == ("fe80::1", 69, 0, 4)
    assert tftp_socket.sendto.call_args_list[1].args[1] == ("fe80::1", 20_069, 0, 4)
    assert tftp_socket.sendto.call_args_list[2].args[1] == ("fe80::1", 20_069, 0, 4)


def test_upload_ipv6_firmware_waits_for_captured_write_request_ack(mocker, tftp_socket, tmp_path):
    """Use the Windows pcap ACK 0 to begin the data transfer."""
    firmware_file = tmp_path / "firmware.lfu"
    firmware_file.write_bytes(b"firmware")
    capture = mocker.MagicMock()
    capture.__enter__.return_value = capture
    capture.read_packet.return_value = _tftp_acknowledgement_frame("fe80::1", 53_000)
    tftp_socket.getsockname.return_value = ("fe80::2", 53_000, 0, 7)
    tftp_socket.recv.return_value = struct.pack("!HH", TFTP_ACK, 1)
    mocker.patch("ingenialink.utils.ipv6_tftp.sys.platform", "win32")
    mocker.patch("ingenialink.utils.ipv6_tftp._get_interface_index", return_value=7)
    mocker.patch("ingenialink.utils.ipv6_tftp.socket.socket", return_value=tftp_socket)
    pcap_capture = mocker.patch("ingenialink.utils.ipv6_tftp.PcapCapture", return_value=capture)

    TftpUploader("fe80::1", r"\Device\NPF_{GUID}").upload_file(firmware_file)

    pcap_capture.assert_called_once_with(r"\Device\NPF_{GUID}")
    capture.read_packet.assert_called_once_with()
    assert tftp_socket.sendto.call_args_list[0].args[1] == ("fe80::1", 69, 0, 7)
    assert tftp_socket.sendto.call_args_list[1].args[1] == ("fe80::1", 20_069, 0, 7)


def test_upload_ipv6_firmware_raises_on_tftp_error(mocker, tftp_socket, tmp_path):
    """Expose server TFTP errors through the standard firmware exception."""
    mocker.patch("ingenialink.utils.ipv6_tftp.sys.platform", "linux")
    firmware_file = tmp_path / "firmware.lfu"
    firmware_file.touch()
    mocker.patch("ingenialink.utils.ipv6_tftp._get_interface_index", return_value=4)
    mocker.patch("ingenialink.utils.ipv6_tftp.socket.socket", return_value=tftp_socket)
    tftp_socket.recv.return_value = b"\0\x05\0\x01access denied\0"

    with pytest.raises(ILFirmwareLoadError, match="TFTP error 1: access denied"):
        TftpUploader("fe80::1", "eth0").upload_file(firmware_file)
