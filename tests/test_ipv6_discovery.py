import socket
import struct

import pytest

from ingenialink.utils.ipv6_discovery import (
    ALL_NODES_MULTICAST_ADDRESS,
    ICMPV6_ECHO_REPLY,
    ICMPV6_ECHO_REQUEST,
    ICMPV6_HEADER_FORMAT,
    _get_echo_reply_source_address,
    _get_interface_index,
    _NpcapCapture,
    discover_ipv6_devices,
)


def test_discover_ipv6_devices_collects_unique_responses(mocker):
    mocker.patch("ingenialink.utils.ipv6_discovery.os.getpid", return_value=123)
    mocker.patch("ingenialink.utils.ipv6_discovery.platform.system", return_value="Linux")
    discovery_socket = mocker.MagicMock()
    discovery_socket.__enter__.return_value = discovery_socket
    discovery_socket.recvfrom.side_effect = [
        (
            struct.pack(ICMPV6_HEADER_FORMAT, ICMPV6_ECHO_REPLY, 0, 0, 123, 0),
            ("fe80::1", 0, 0, 4),
        ),
        (b"unrelated", ("fe80::3", 0, 0, 4)),
        (
            struct.pack(ICMPV6_HEADER_FORMAT, ICMPV6_ECHO_REPLY, 0, 0, 123, 0),
            ("fe80::2", 0, 0, 4),
        ),
        (
            struct.pack(ICMPV6_HEADER_FORMAT, ICMPV6_ECHO_REPLY, 0, 0, 123, 0),
            ("fe80::1", 0, 0, 4),
        ),
        socket.timeout,
    ]
    mocker.patch("ingenialink.utils.ipv6_discovery.socket.if_nametoindex", return_value=4)
    socket_factory = mocker.patch(
        "ingenialink.utils.ipv6_discovery.socket.socket", return_value=discovery_socket
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
    assert destination == (ALL_NODES_MULTICAST_ADDRESS, 0, 0, 4)


@pytest.mark.parametrize(
    "timeout_s",
    [
        0.0,
        -1.0,
    ],
)
def test_discover_ipv6_devices_rejects_invalid_timeout(timeout_s):
    with pytest.raises(ValueError):
        discover_ipv6_devices("Ethernet", timeout_s)


def test_get_interface_index_uses_npcap_guid_on_windows(mocker):
    adapter = mocker.Mock(AdapterName="{AB6ECF19-612D-4265-ABD5-0F9A286A6962}", Ipv6IfIndex=7)
    mocker.patch("ingenialink.utils.ipv6_discovery.platform.system", return_value="Windows")
    get_windows_ipv6_adapters = mocker.patch(
        "ingenialink.utils.ipv6_discovery._get_windows_ipv6_adapters",
        return_value=[adapter],
    )

    interface_index = _get_interface_index(r"\Device\NPF_{AB6ECF19-612D-4265-ABD5-0F9A286A6962}")

    assert interface_index == 7
    get_windows_ipv6_adapters.assert_called_once_with()


def test_get_interface_index_uses_native_interface_name_outside_windows(mocker):
    mocker.patch("ingenialink.utils.ipv6_discovery.platform.system", return_value="Linux")
    if_nametoindex = mocker.patch(
        "ingenialink.utils.ipv6_discovery.socket.if_nametoindex",
        return_value=4,
    )

    assert _get_interface_index("eth0") == 4
    if_nametoindex.assert_called_once_with("eth0")


def test_discover_ipv6_devices_uses_npcap_on_windows(mocker):
    events = []
    capture = mocker.MagicMock()
    capture.__enter__.return_value = capture
    capture.read_packet.side_effect = [None, None]
    mocker.patch("ingenialink.utils.ipv6_discovery.os.getpid", return_value=123)
    mocker.patch("ingenialink.utils.ipv6_discovery.platform.system", return_value="Windows")
    mocker.patch("ingenialink.utils.ipv6_discovery._get_interface_index", return_value=4)
    npcac_capture = mocker.patch(
        "ingenialink.utils.ipv6_discovery._NpcapCapture",
        side_effect=lambda _: events.append("capture_started") or capture,
        return_value=capture,
    )
    discovery_socket = mocker.MagicMock()
    discovery_socket.__enter__.return_value = discovery_socket
    discovery_socket.sendto.side_effect = lambda *_: events.append("request_sent")
    mocker.patch(
        "ingenialink.utils.ipv6_discovery.socket.socket",
        return_value=discovery_socket,
    )
    mocker.patch(
        "ingenialink.utils.ipv6_discovery.time.monotonic",
        side_effect=[0.0, 0.5, 1.0],
    )

    assert discover_ipv6_devices(r"\Device\NPF_{AB6ECF19-612D-4265-ABD5-0F9A286A6962}") == []

    npcac_capture.assert_called_once_with(r"\Device\NPF_{AB6ECF19-612D-4265-ABD5-0F9A286A6962}")
    assert events == ["capture_started", "request_sent"]


def test_get_echo_reply_source_address_returns_matching_ipv6_source():
    source_address = "fe80::1"
    ethernet_header = bytes(12) + b"\x86\xdd"
    ipv6_header = b"\x60" + bytes(5) + bytes([58]) + bytes(1)
    ipv6_header += socket.inet_pton(socket.AF_INET6, source_address) + bytes(16)
    echo_reply = struct.pack(ICMPV6_HEADER_FORMAT, ICMPV6_ECHO_REPLY, 0, 0, 123, 0)

    assert (
        _get_echo_reply_source_address(ethernet_header + ipv6_header + echo_reply, 123)
        == source_address
    )


def test_npcap_capture_applies_icmp6_filter(mocker):
    library = mocker.MagicMock()
    library.pcap_open_live.return_value = 1
    library.pcap_datalink.return_value = 1
    library.pcap_compile.return_value = 0
    library.pcap_setfilter.return_value = 0
    mocker.patch("ingenialink.utils.ipv6_discovery.ctypes.CDLL", return_value=library)

    capture = _NpcapCapture(r"\Device\NPF_{AB6ECF19-612D-4265-ABD5-0F9A286A6962}")

    assert library.pcap_compile.call_args.args[2] == b"icmp6"
    library.pcap_freecode.assert_called_once()
    capture.__exit__()


def test_npcap_capture_reports_missing_library(mocker):
    mocker.patch(
        "ingenialink.utils.ipv6_discovery.ctypes.CDLL",
        side_effect=OSError("wpcap.dll not found"),
    )

    with pytest.raises(OSError, match="Npcap is required for IPv6 discovery on Windows"):
        _NpcapCapture("Ethernet")
