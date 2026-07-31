"""Cross-platform network interface resolution."""

import ipaddress
import re

import ifaddr

PCAP_INTERFACE_GUID_PATTERN = re.compile(
    r"^\\Device\\NPF_(\{[^}]+\})$",
    re.IGNORECASE,
)


def get_interface_ipv4_subnet(interface: str) -> ipaddress.IPv4Network:
    """Return the IPv4 subnet configured for an interface.

    Args:
        interface: System interface name or Pcap device path.

    Returns:
        IPv4 subnet configured for the interface.

    Raises:
        OSError: If the interface cannot be found or has no IPv4 address.
    """
    interface_name = _normalize_interface_name(interface)

    for adapter in ifaddr.get_adapters():
        if not _interface_matches(adapter, interface_name):
            continue

        for adapter_ip in adapter.ips:
            if not isinstance(adapter_ip.ip, str):
                continue

            ip_address = ipaddress.ip_address(adapter_ip.ip)
            if isinstance(ip_address, ipaddress.IPv4Address):
                return ipaddress.IPv4Network(
                    f"{ip_address}/{adapter_ip.network_prefix}",
                    strict=False,
                )

        raise OSError(f"The interface '{interface}' has no configured IPv4 address.")

    raise OSError(f"The interface '{interface}' could not be found.")


def _normalize_interface_name(interface: str) -> str:
    """Normalize a system interface name or Pcap device path.

    Args:
        interface: System interface name or Pcap device path.

    Returns:
        Normalized interface name or Pcap device path.

    """
    guid_match = PCAP_INTERFACE_GUID_PATTERN.fullmatch(interface)
    if guid_match is not None:
        return guid_match.group(1).casefold()

    return interface.casefold()


def _interface_matches(adapter: ifaddr.Adapter, interface: str) -> bool:
    """Check whether an adapter matches an interface identifier.

    Args:
        adapter: The adapter to check.
        interface: The interface identifier to match against.

    Returns:
        True if the adapter matches the interface identifier, False otherwise.

    """
    return adapter.name.casefold() == interface or adapter.nice_name.casefold() == interface
