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


def test_upload_ipv6_firmware_uses_scoped_address_and_uploads_file(mocker, tftp_socket, tmp_path):
    """Upload a final data block using the discovery interface index."""
    firmware_file = tmp_path / "firmware.lfu"
    firmware_file.write_bytes(b"firmware")
    interface_index = mocker.patch(
        "ingenialink.utils.ipv6_tftp._get_interface_index", return_value=7
    )
    socket_factory = mocker.patch(
        "ingenialink.utils.ipv6_tftp.socket.socket", return_value=tftp_socket
    )
    tftp_socket.recvfrom.return_value = (struct.pack("!HH", TFTP_ACK, 0), ("fe80::1", 1234, 0, 7))
    tftp_socket.recv.return_value = struct.pack("!HH", TFTP_ACK, 1)

    TftpUploader("fe80::1", r"\Device\NPF_{GUID}").upload_file(firmware_file)

    interface_index.assert_called_once_with(r"\Device\NPF_{GUID}")
    socket_factory.assert_called_once_with(socket.AF_INET6, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    write_request, destination = tftp_socket.sendto.call_args.args
    assert destination == ("fe80::1", 69, 0, 7)
    assert struct.unpack("!H", write_request[:2])[0] == TFTP_WRQ
    tftp_socket.connect.assert_called_once_with(("fe80::1", 1234, 0, 7))
    data_packet = tftp_socket.send.call_args.args[0]
    assert struct.unpack("!HH", data_packet[:4]) == (TFTP_DATA, 1)
    assert data_packet[4:] == b"firmware"


def test_upload_ipv6_firmware_rejects_non_lfu_file(tmp_path):
    """Reject files the drive TFTP server cannot accept before using sockets."""
    firmware_file = tmp_path / "firmware.bin"
    firmware_file.touch()

    with pytest.raises(ILFirmwareLoadError, match="only accepts .lfu"):
        TftpUploader("fe80::1", "eth0").upload_file(firmware_file)


def test_upload_ipv6_firmware_raises_on_tftp_error(mocker, tftp_socket, tmp_path):
    """Expose server TFTP errors through the standard firmware exception."""
    firmware_file = tmp_path / "firmware.lfu"
    firmware_file.touch()
    mocker.patch("ingenialink.utils.ipv6_tftp._get_interface_index", return_value=4)
    mocker.patch("ingenialink.utils.ipv6_tftp.socket.socket", return_value=tftp_socket)
    tftp_socket.recvfrom.return_value = b"\0\x05\0\x01access denied\0", ("fe80::1", 69, 0, 4)

    with pytest.raises(ILFirmwareLoadError, match="TFTP error 1: access denied"):
        TftpUploader("fe80::1", "eth0").upload_file(firmware_file)
