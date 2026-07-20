import importlib
import os
import platform
import re
import socket
import struct
import time
from typing import cast

ALL_NODES_MULTICAST_ADDRESS = "ff02::1"
ICMPV6_ECHO_REQUEST = 128
ICMPV6_ECHO_REPLY = 129
ICMPV6_HEADER_FORMAT = "!BBHHH"
ICMPV6_SEQUENCE_NUMBER = 0
MAX_ICMPV6_PACKET_SIZE = 65_535
NPCAP_INTERFACE_GUID_PATTERN = re.compile(r"^\\Device\\NPF_(\{[^}]+\})$", re.IGNORECASE)


def discover_ipv6_devices(
    interface: str,
    timeout_s: float = 1.0,
) -> list[str]:
    r"""Discover IPv6 devices that reply to an ICMPv6 all-nodes echo request.

    Args:
        interface: Network interface to scan. On Windows, this accepts the
            Npcap device path used by EtherCAT, for example
            ``\\Device\\NPF_{AB6ECF19-612D-4265-ABD5-0F9A286A6962}``.
        timeout_s: Maximum time in seconds to collect responses.

    Returns:
        Unique IPv6 addresses of responding devices, in response order.

    Raises:
        ValueError: If the timeout is invalid.
        OSError: If the network interface or socket cannot be configured.
    """
    _validate_timeout(timeout_s)
    interface_index = _get_interface_index(interface)
    deadline = time.monotonic() + timeout_s
    discovered_devices: dict[str, None] = {}
    echo_identifier = os.getpid() & 0xFFFF
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
            struct.pack("=I", interface_index),
        )
        discovery_socket.sendto(
            echo_request,
            (ALL_NODES_MULTICAST_ADDRESS, 0, 0, interface_index),
        )

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
    if platform.system() != "Windows":
        return socket.if_nametoindex(interface)

    guid_match = NPCAP_INTERFACE_GUID_PATTERN.fullmatch(interface)
    if guid_match is None:
        return socket.if_nametoindex(interface)

    get_adapters_addresses = importlib.import_module("ingenialink.get_adapters_addresses")

    interface_guid = guid_match.group(1).upper()
    adapters = get_adapters_addresses.get_adapters_addresses(
        adapter_families=get_adapters_addresses.AdapterFamily.INET6,
        scan_flags=[get_adapters_addresses.ScanFlags.INCLUDE_ALL_INTERFACES],
    )
    for adapter in adapters:
        if adapter.AdapterName == interface_guid:
            return cast("int", adapter.Ipv6IfIndex)
    raise OSError(f"The Npcap interface '{interface}' could not be found.")


def _is_echo_reply(response: bytes, identifier: int) -> bool:
    if len(response) < struct.calcsize(ICMPV6_HEADER_FORMAT):
        return False
    message_type, code, _, response_identifier, sequence_number = cast(
        "tuple[int, int, int, int, int]",
        struct.unpack(
            ICMPV6_HEADER_FORMAT,
            response[: struct.calcsize(ICMPV6_HEADER_FORMAT)],
        ),
    )
    return (
        message_type == ICMPV6_ECHO_REPLY
        and code == 0
        and response_identifier == identifier
        and sequence_number == ICMPV6_SEQUENCE_NUMBER
    )


def _validate_timeout(timeout_s: float) -> None:
    if timeout_s <= 0:
        raise ValueError("The discovery timeout must be greater than zero.")
