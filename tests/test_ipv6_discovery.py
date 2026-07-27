import socket
import struct

import pytest

from ingenialink.ethernet.tsn.interfaces import _get_interface_index
from ingenialink.ethernet.tsn.ipv6_discovery import (
    ALL_NODES_IPV6_ADDRESS,
    ICMPV6_ECHO_REPLY,
    ICMPV6_ECHO_REQUEST,
    ICMPV6_HEADER_FORMAT,
    _get_echo_reply_source_address,
    discover_ipv6_devices,
)


def _echo_reply_packet(identifier):
    return struct.pack(ICMPV6_HEADER_FORMAT, ICMPV6_ECHO_REPLY, 0, 0, identifier, 0)


def _ethernet_ipv6_header(source_address, next_header):
    ethernet_header = bytes(12) + b"\x86\xdd"
    ipv6_header = b"\x60" + bytes(5) + bytes([next_header]) + bytes(1)
    return (
        ethernet_header
        + ipv6_header
        + socket.inet_pton(socket.AF_INET6, source_address)
        + bytes(16)
    )


@pytest.fixture
def discovery_socket(mocker):
    """Provide a raw-socket mock that supports the discovery context manager.

    Returns:
        A socket mock configured for use in a ``with`` statement.
    """
    socket_mock = mocker.MagicMock()
    socket_mock.__enter__.return_value = socket_mock
    return socket_mock


def test_discover_ipv6_devices_collects_unique_responses(mocker, discovery_socket):
    """Collect matching Linux responses once and preserve their response order."""
    mocker.patch("ingenialink.ethernet.tsn.ipv6_discovery.secrets.randbelow", return_value=122)
    mocker.patch("ingenialink.ethernet.tsn.ipv6_discovery.sys.platform", "linux")
    discovery_socket.recvfrom.side_effect = [
        (
            _echo_reply_packet(123),
            ("fe80::1", 0, 0, 4),
        ),
        (b"unrelated", ("fe80::3", 0, 0, 4)),
        (
            _echo_reply_packet(123),
            ("fe80::2", 0, 0, 4),
        ),
        (
            _echo_reply_packet(123),
            ("fe80::1", 0, 0, 4),
        ),
        socket.timeout,
    ]
    mocker.patch("ingenialink.ethernet.tsn.interfaces.socket.if_nametoindex", return_value=4)
    socket_factory = mocker.patch(
        "ingenialink.ethernet.tsn.ipv6_discovery.socket.socket", return_value=discovery_socket
    )

    devices = discover_ipv6_devices("Ethernet", timeout_s=1.0)

    assert devices == ["fe80::1", "fe80::2"]
    socket_factory.assert_called_once_with(socket.AF_INET6, socket.SOCK_RAW, socket.IPPROTO_ICMPV6)
    discovery_socket.setsockopt.assert_called_once_with(
        socket.IPPROTO_IPV6,
        socket.IPV6_MULTICAST_IF,
        4,
    )
    request, destination = discovery_socket.sendto.call_args.args
    assert request[0] == ICMPV6_ECHO_REQUEST
    assert destination == (ALL_NODES_IPV6_ADDRESS, 0, 0, 4)


@pytest.mark.parametrize(
    "timeout_s",
    [
        0.0,
        -1.0,
    ],
)
def test_discover_ipv6_devices_rejects_invalid_timeout(timeout_s):
    """Reject zero and negative timeouts before configuring a socket."""
    with pytest.raises(ValueError):
        discover_ipv6_devices("Ethernet", timeout_s)


def test_get_interface_index_uses_pcap_guid_on_windows(mocker):
    """Map a Pcap interface GUID to its Windows IPv6 interface index."""
    adapter = mocker.Mock(AdapterName="{DEADC0FF-EEEE-4444-8888-2BF6900CBFA0}", Ipv6IfIndex=7)
    mocker.patch("ingenialink.ethernet.tsn.interfaces.sys.platform", "win32")
    get_windows_ipv6_adapters = mocker.patch(
        "ingenialink.ethernet.tsn.interfaces._get_windows_ipv6_adapters",
        return_value=[adapter],
        create=True,
    )

    interface_index = _get_interface_index(r"\Device\NPF_{DEADC0FF-EEEE-4444-8888-2BF6900CBFA0}")

    assert interface_index == 7
    get_windows_ipv6_adapters.assert_called_once_with()


def test_get_interface_index_uses_native_interface_name_outside_windows(mocker):
    """Use the native socket interface lookup outside Windows."""
    mocker.patch("ingenialink.ethernet.tsn.interfaces.sys.platform", "linux")
    if_nametoindex = mocker.patch(
        "ingenialink.ethernet.tsn.interfaces.socket.if_nametoindex",
        return_value=4,
    )

    assert _get_interface_index("eth0") == 4
    if_nametoindex.assert_called_once_with("eth0")


def test_discover_ipv6_devices_uses_pcap_on_windows(mocker, discovery_socket):
    """Start pcap capture before sending the multicast request on Windows."""
    events = []
    capture = mocker.MagicMock()
    capture.__enter__.return_value = capture
    capture.read_packet.side_effect = [None, None]
    mocker.patch("ingenialink.ethernet.tsn.ipv6_discovery.secrets.randbelow", return_value=122)
    mocker.patch("ingenialink.ethernet.tsn.ipv6_discovery.sys.platform", "win32")
    mocker.patch("ingenialink.ethernet.tsn.interfaces.sys.platform", "win32")
    mocker.patch("ingenialink.ethernet.tsn.interfaces._get_interface_index", return_value=4)
    pcap_capture = mocker.patch(
        "ingenialink.ethernet.tsn.ipv6_discovery.PcapCapture",
        side_effect=lambda _: events.append("capture_started") or capture,
        create=True,
    )
    discovery_socket.sendto.side_effect = lambda *_: events.append("request_sent")
    mocker.patch(
        "ingenialink.ethernet.tsn.ipv6_discovery.socket.socket",
        return_value=discovery_socket,
    )
    mocker.patch(
        "ingenialink.ethernet.tsn.ipv6_discovery.time.monotonic",
        side_effect=[0.0, 0.5, 1.0],
    )

    assert discover_ipv6_devices(r"\Device\NPF_{DEADC0FF-EEEE-4444-8888-2BF6900CBFA0}") == []

    pcap_capture.assert_called_once_with(r"\Device\NPF_{DEADC0FF-EEEE-4444-8888-2BF6900CBFA0}")
    assert events == ["capture_started", "request_sent"]


def test_get_echo_reply_source_address_returns_matching_ipv6_source():
    """Extract the IPv6 source from an Ethernet-framed matching echo reply."""
    source_address = "fe80::1"

    assert (
        _get_echo_reply_source_address(
            _ethernet_ipv6_header(source_address, 58) + _echo_reply_packet(123),
            123,
        )
        == source_address
    )


def test_get_echo_reply_source_address_rejects_invalid_ipv6_version():
    """Ignore Ethernet frames that do not contain an IPv6 header."""
    packet = bytes(12) + b"\x86\xdd" + bytes(40)

    assert _get_echo_reply_source_address(packet, 123) is None


def test_get_echo_reply_source_address_ignores_non_initial_fragment():
    """Ignore echo replies that are not contained in the first IPv6 fragment."""
    fragment_header = bytes([58, 0, 0, 8]) + bytes(4)

    assert (
        _get_echo_reply_source_address(
            _ethernet_ipv6_header("::", 44) + fragment_header + _echo_reply_packet(123),
            123,
        )
        is None
    )
