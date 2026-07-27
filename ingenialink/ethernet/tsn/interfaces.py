"""Cross-platform IPv6 interface-index resolution."""

import re
import socket
import sys
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class _WindowsIpv6Adapter:
    AdapterName: str
    Ipv6IfIndex: int


PCAP_INTERFACE_GUID_PATTERN = re.compile(r"^\\Device\\NPF_(\{[^}]+\})$", re.IGNORECASE)


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

    from ingenialink.get_adapters_addresses import (  # type: ignore[import-not-found, unused-ignore, import-untyped]  # noqa: PLC0415
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
