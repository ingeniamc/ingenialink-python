"""Discover IPv6 devices using raw sockets on Linux and pcap capture on Windows."""

import re
import secrets
import socket
import struct
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Optional

if sys.platform == "win32":
    import cypcap  # type: ignore[import-untyped]


@dataclass(frozen=True)
class _WindowsIpv6Adapter:
    AdapterName: str
    Ipv6IfIndex: int


# Discovery constants
ALL_NODES_IPV6_ADDRESS = "ff02::1"
ICMPV6_ECHO_REQUEST = 128
ICMPV6_ECHO_REPLY = 129
ICMPV6_HEADER_FORMAT = "!BBHHH"
ICMPV6_HEADER_SIZE = struct.calcsize(ICMPV6_HEADER_FORMAT)
ICMPV6_SEQUENCE_NUMBER = 0
MAX_ICMPV6_PACKET_SIZE = 65_535
PCAP_INTERFACE_GUID_PATTERN = re.compile(r"^\\Device\\NPF_(\{[^}]+\})$", re.IGNORECASE)

# Pcap constants
PCAP_READ_TIMEOUT_S = 0.01

# Ethernet constants
ETHERNET_HEADER_SIZE = 14
ETHERNET_TYPE_OFFSET = 12
ETHERTYPE_IPV6 = 0x86DD
VLAN_ETHERTYPES = {0x8100, 0x88A8, 0x9100}

# IPv6 constants
IPV6_HEADER_SIZE = 40
IPV6_NEXT_HEADER_OFFSET = 6
IPV6_SOURCE_ADDRESS_OFFSET = 8
IPV6_HOP_BY_HOP = 0
IPV6_ROUTING = 43
IPV6_FRAGMENT = 44
IPV6_AUTHENTICATION = 51
IPV6_DESTINATION_OPTIONS = 60
IPV6_NEXT_HEADER_ICMPV6 = 58
IPV6_FRAGMENT_OFFSET_MASK = 0xFFF8


class _PcapCapture:
    """Pcap packet capture for a single network interface."""

    def __init__(self, interface: str) -> None:
        self._capture = None
        try:
            self._capture = cypcap.create(interface)
            self._capture.set_snaplen(MAX_ICMPV6_PACKET_SIZE)
            self._capture.set_promisc(False)
            self._capture.set_timeout(PCAP_READ_TIMEOUT_S)
            self._capture.activate()
            if self._capture.datalink() != cypcap.DatalinkType.EN10MB:
                raise OSError("Pcap discovery requires an Ethernet interface.")
            self._capture.setfilter("ip6 or (vlan and ip6)")
        except cypcap.Error as error:
            self.close()
            raise OSError(f"Unable to configure pcap capture: {error}") from error
        except OSError:
            self.close()
            raise

    def __enter__(self) -> "_PcapCapture":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the pcap capture handle once.

        Raises:
            OSError: If cypcap cannot close the capture.
        """
        if self._capture is not None:
            capture = self._capture
            self._capture = None
            try:
                capture.close()
            except cypcap.Error as error:
                raise OSError(f"Unable to close pcap capture: {error}") from error

    def read_packet(self) -> Optional[bytes]:
        if self._capture is None:
            raise OSError("Pcap capture handle is closed.")
        try:
            packet_header, packet_data = next(self._capture)
        except cypcap.Error as error:
            raise OSError(f"Unable to read pcap packet: {error}") from error
        except StopIteration as error:
            raise OSError("Pcap capture terminated unexpectedly.") from error
        if packet_header is None:
            return None
        return bytes(packet_data)


def discover_ipv6_devices(
    interface: str,
    timeout_s: float = 1.0,
) -> list[str]:
    r"""Discover IPv6 devices that reply to an ICMPv6 all-nodes echo request.

    Args:
        interface: Network interface to scan. On Linux, provide the native
            interface name, such as ``eth0`` or ``enp3s0``. On Windows,
            provide the Npcap device path used by EtherCAT, such as
            ``\\Device\\NPF_{DEADC0FF-EEEE-4444-8888-2BF6900CBFA0}``.
        timeout_s: Maximum time in seconds to collect responses.

    Returns:
        Unique IPv6 addresses of responding devices, in response order.

    Raises:
        ValueError: If the timeout is invalid.
        OSError: If the network interface or socket cannot be configured.
    """
    _validate_timeout(timeout_s)
    interface_index = _get_interface_index(interface)
    echo_identifier = secrets.randbelow(0xFFFF) + 1
    echo_request = struct.pack(
        ICMPV6_HEADER_FORMAT,
        ICMPV6_ECHO_REQUEST,
        0,
        0,
        echo_identifier,
        ICMPV6_SEQUENCE_NUMBER,
    )

    with socket.socket(socket.AF_INET6, socket.SOCK_RAW, socket.IPPROTO_ICMPV6) as discovery_socket:
        discovery_socket.setsockopt(
            socket.IPPROTO_IPV6,
            socket.IPV6_MULTICAST_IF,
            interface_index,
        )
        if sys.platform == "win32":
            # Windows raw sockets cannot receive multicast ICMPv6 replies.
            with _PcapCapture(interface) as capture:
                deadline = time.monotonic() + timeout_s
                discovery_socket.sendto(
                    echo_request,
                    (ALL_NODES_IPV6_ADDRESS, 0, 0, interface_index),
                )
                return _capture_pcap_responses(capture, echo_identifier, deadline)

        deadline = time.monotonic() + timeout_s
        discovery_socket.sendto(
            echo_request,
            (ALL_NODES_IPV6_ADDRESS, 0, 0, interface_index),
        )
        return _receive_socket_responses(discovery_socket, echo_identifier, deadline)


def _capture_pcap_responses(
    capture: _PcapCapture,
    echo_identifier: int,
    deadline: float,
) -> list[str]:
    discovered_devices: dict[str, None] = {}
    while time.monotonic() < deadline:
        packet = capture.read_packet()
        if packet is None:
            continue
        source_address = _get_echo_reply_source_address(packet, echo_identifier)
        if source_address is not None:
            discovered_devices[source_address] = None
    return list(discovered_devices)


def _receive_socket_responses(
    discovery_socket: socket.socket,
    echo_identifier: int,
    deadline: float,
) -> list[str]:
    discovered_devices: dict[str, None] = {}
    while (remaining_time_s := deadline - time.monotonic()) > 0:
        discovery_socket.settimeout(remaining_time_s)
        try:
            response, source_address = discovery_socket.recvfrom(MAX_ICMPV6_PACKET_SIZE)
        except socket.timeout:
            break
        if _is_echo_reply(response, echo_identifier):
            discovered_devices[source_address[0]] = None
    return list(discovered_devices)


def _get_interface_index(interface: str) -> int:
    """Return the IPv6 index for a system interface or Pcap device path.

    Raises:
        OSError: If the interface cannot be resolved.
    """
    if sys.platform == "win32":
        guid_match = PCAP_INTERFACE_GUID_PATTERN.fullmatch(interface)
        if guid_match is None:
            return socket.if_nametoindex(interface)

        interface_guid = guid_match.group(1).upper()
        for adapter in _get_windows_ipv6_adapters():
            if adapter.AdapterName == interface_guid:
                return adapter.Ipv6IfIndex
        raise OSError(f"The pcap interface '{interface}' could not be found.")

    return socket.if_nametoindex(interface)


def _get_windows_ipv6_adapters() -> Sequence[_WindowsIpv6Adapter]:
    """Return all Windows adapters with IPv6 information.

    Raises:
        OSError: If called outside Windows.
    """
    if sys.platform != "win32":
        raise OSError("Windows IPv6 adapters are only available on Windows.")

    from ingenialink.get_adapters_addresses import (  # noqa: PLC0415
        AdapterFamily,
        ScanFlags,
        get_adapters_addresses,
    )

    adapters = get_adapters_addresses(
        adapter_families=AdapterFamily.INET6,
        scan_flags=[ScanFlags.INCLUDE_ALL_INTERFACES],
    )

    return [
        _WindowsIpv6Adapter(
            AdapterName=adapter.AdapterName,
            Ipv6IfIndex=adapter.Ipv6IfIndex,
        )
        for adapter in adapters
    ]


def _is_echo_reply(response: bytes, identifier: int) -> bool:
    if len(response) < ICMPV6_HEADER_SIZE:
        return False
    return (
        response[0] == ICMPV6_ECHO_REPLY
        and response[1] == 0
        and int.from_bytes(response[4:6], "big") == identifier
        and int.from_bytes(response[6:8], "big") == ICMPV6_SEQUENCE_NUMBER
    )


def _get_echo_reply_source_address(packet: bytes, identifier: int) -> Optional[str]:
    """Extract the source from a matching echo reply in an Ethernet frame.

    Returns:
        The source address, or ``None`` when the packet is not a matching reply.
    """
    ipv6_offset = _get_ipv6_offset(packet)
    if ipv6_offset is None or len(packet) < ipv6_offset + IPV6_HEADER_SIZE:
        return None
    if packet[ipv6_offset] >> 4 != 6:
        return None
    next_header = packet[ipv6_offset + IPV6_NEXT_HEADER_OFFSET]
    icmp_offset = ipv6_offset + IPV6_HEADER_SIZE
    while next_header != IPV6_NEXT_HEADER_ICMPV6:
        extension_header = _get_ipv6_extension_header(packet, icmp_offset, next_header)
        if extension_header is None:
            return None
        next_header, icmp_offset = extension_header
    if not _is_echo_reply(packet[icmp_offset:], identifier):
        return None
    source_address = packet[
        ipv6_offset + IPV6_SOURCE_ADDRESS_OFFSET : ipv6_offset + IPV6_SOURCE_ADDRESS_OFFSET + 16
    ]
    return socket.inet_ntop(socket.AF_INET6, source_address)


def _get_ipv6_offset(packet: bytes) -> Optional[int]:
    """Locate an IPv6 header after Ethernet and optional VLAN headers.

    Returns:
        The IPv6 header offset, or ``None`` when the frame does not contain IPv6.
    """
    if len(packet) < ETHERNET_HEADER_SIZE:
        return None
    ethernet_type = int.from_bytes(
        packet[ETHERNET_TYPE_OFFSET : ETHERNET_TYPE_OFFSET + 2],
        "big",
    )
    ipv6_offset = ETHERNET_HEADER_SIZE
    while ethernet_type in VLAN_ETHERTYPES:
        if len(packet) < ipv6_offset + 4:
            return None
        ethernet_type = int.from_bytes(packet[ipv6_offset + 2 : ipv6_offset + 4], "big")
        ipv6_offset += 4
    if ethernet_type != ETHERTYPE_IPV6:
        return None
    return ipv6_offset


def _get_ipv6_extension_header(
    packet: bytes,
    offset: int,
    header_type: int,
) -> Optional[tuple[int, int]]:
    """Return the next header and offset after a supported extension header."""
    if len(packet) < offset + 2:
        return None
    next_header = packet[offset]
    if header_type == IPV6_FRAGMENT:
        if len(packet) < offset + 8:
            return None
        fragment_offset = int.from_bytes(packet[offset + 2 : offset + 4], "big")
        if fragment_offset & IPV6_FRAGMENT_OFFSET_MASK:
            return None
        header_size = 8
    elif header_type == IPV6_AUTHENTICATION:
        header_size = (packet[offset + 1] + 2) * 4
    elif header_type in {
        IPV6_HOP_BY_HOP,
        IPV6_ROUTING,
        IPV6_DESTINATION_OPTIONS,
    }:
        header_size = (packet[offset + 1] + 1) * 8
    else:
        return None
    if len(packet) < offset + header_size:
        return None
    return next_header, offset + header_size


def _validate_timeout(timeout_s: float) -> None:
    if timeout_s <= 0:
        raise ValueError("The discovery timeout must be greater than zero.")
