"""Discover IPv6 devices using raw sockets on Linux and pcap capture on Windows."""

import ctypes
import os
import re
import secrets
import socket
import struct
import sys
import time
from typing import Optional

if sys.platform == "win32":
    from ingenialink.get_adapters_addresses import (
        AdapterFamily,
        CyAdapter,
        ScanFlags,
        get_adapters_addresses,
    )

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
PCAP_READ_TIMEOUT_MS = 10
PCAP_ERRBUF_SIZE = 256
DLT_EN10MB = 1

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


class _TimeVal(ctypes.Structure):
    _fields_ = [
        ("tv_sec", ctypes.c_long),
        ("tv_usec", ctypes.c_long),
    ]


class _PcapPacketHeader(ctypes.Structure):
    _fields_ = [
        ("ts", _TimeVal),
        ("caplen", ctypes.c_uint32),
        ("len", ctypes.c_uint32),
    ]


class _BpfProgram(ctypes.Structure):
    _fields_ = [
        ("bf_len", ctypes.c_uint),
        ("bf_insns", ctypes.c_void_p),
    ]


class _PcapCapture:
    """Pcap packet capture for a single network interface."""

    def __init__(self, interface: str) -> None:
        self._library = _load_pcap_library()
        self._handle: Optional[int] = None
        self._configure_library()
        error_buffer = ctypes.create_string_buffer(PCAP_ERRBUF_SIZE)
        self._handle = self._library.pcap_open_live(
            interface.encode(),
            MAX_ICMPV6_PACKET_SIZE,
            0,
            PCAP_READ_TIMEOUT_MS,
            error_buffer,
        )
        if not self._handle:
            raise OSError(error_buffer.value.decode(errors="replace"))
        if self._library.pcap_datalink(self._handle) != DLT_EN10MB:
            self.close()
            raise OSError("Pcap discovery requires an Ethernet interface.")
        try:
            self._apply_ipv6_filter()
        except OSError:
            self.close()
            raise

    def __enter__(self) -> "_PcapCapture":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the pcap capture handle once."""
        if self._handle is not None:
            self._library.pcap_close(self._handle)
            self._handle = None

    def read_packet(self) -> Optional[bytes]:
        if self._handle is None:
            raise OSError("Pcap capture handle is closed.")
        packet_header = ctypes.POINTER(_PcapPacketHeader)()
        packet_data = ctypes.POINTER(ctypes.c_ubyte)()
        result = self._library.pcap_next_ex(
            self._handle,
            ctypes.byref(packet_header),
            ctypes.byref(packet_data),
        )
        if result == 1:
            return ctypes.string_at(packet_data, packet_header.contents.caplen)
        if result == 0:
            return None
        if result == -2:
            raise OSError("Pcap capture terminated unexpectedly.")
        error_message = self._library.pcap_geterr(self._handle).decode(errors="replace")
        raise OSError(error_message)

    def _configure_library(self) -> None:
        self._library.pcap_open_live.argtypes = [
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_char),
        ]
        self._library.pcap_open_live.restype = ctypes.c_void_p
        self._library.pcap_datalink.argtypes = [ctypes.c_void_p]
        self._library.pcap_datalink.restype = ctypes.c_int
        self._library.pcap_close.argtypes = [ctypes.c_void_p]
        self._library.pcap_close.restype = None
        self._library.pcap_next_ex.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.POINTER(_PcapPacketHeader)),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
        ]
        self._library.pcap_next_ex.restype = ctypes.c_int
        self._library.pcap_geterr.argtypes = [ctypes.c_void_p]
        self._library.pcap_geterr.restype = ctypes.c_char_p
        self._library.pcap_compile.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_BpfProgram),
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_uint32,
        ]
        self._library.pcap_compile.restype = ctypes.c_int
        self._library.pcap_setfilter.argtypes = [ctypes.c_void_p, ctypes.POINTER(_BpfProgram)]
        self._library.pcap_setfilter.restype = ctypes.c_int
        self._library.pcap_freecode.argtypes = [ctypes.POINTER(_BpfProgram)]
        self._library.pcap_freecode.restype = None

    def _apply_ipv6_filter(self) -> None:
        filter_program = _BpfProgram()
        if (
            self._library.pcap_compile(
                self._handle,
                ctypes.byref(filter_program),
                b"ip6 or (vlan and ip6)",
                1,
                0,
            )
            != 0
        ):
            raise OSError(self._library.pcap_geterr(self._handle).decode(errors="replace"))
        try:
            if self._library.pcap_setfilter(self._handle, ctypes.byref(filter_program)) != 0:
                raise OSError(self._library.pcap_geterr(self._handle).decode(errors="replace"))
        finally:
            self._library.pcap_freecode(ctypes.byref(filter_program))


def _load_pcap_library() -> ctypes.CDLL:
    system_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
    pcap_library_path = os.path.join(system_root, "System32", "Npcap", "wpcap.dll")
    pcap_directory = os.path.dirname(pcap_library_path)
    if sys.platform == "win32" and os.path.isdir(pcap_directory):
        try:
            with os.add_dll_directory(pcap_directory):
                return ctypes.CDLL(pcap_library_path)
        except OSError:
            pass
    try:
        return ctypes.CDLL("wpcap.dll")
    except OSError as error:
        raise OSError(
            "A pcap-compatible library is required for IPv6 discovery on Windows. "
            "Install a pcap-compatible library and ensure wpcap.dll is available."
        ) from error


def discover_ipv6_devices(
    interface: str,
    timeout_s: float = 1.0,
) -> list[str]:
    r"""Discover IPv6 devices that reply to an ICMPv6 all-nodes echo request.

    Args:
        interface: Network interface to scan. On Windows, this accepts the
            Pcap device path used by EtherCAT, for example
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


def _get_windows_ipv6_adapters() -> list["CyAdapter"]:
    """Return all Windows adapters with IPv6 information.

    Raises:
        OSError: If called outside Windows.
    """
    if sys.platform != "win32":
        raise OSError("Windows IPv6 adapters are only available on Windows.")

    return get_adapters_addresses(
        adapter_families=AdapterFamily.INET6,
        scan_flags=[ScanFlags.INCLUDE_ALL_INTERFACES],
    )


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
