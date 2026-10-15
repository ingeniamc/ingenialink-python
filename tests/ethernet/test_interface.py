"""Tests for Ethernet interface utilities."""

import ipaddress
from types import SimpleNamespace
from typing import Union

import pytest

from ingenialink.ethernet.interface import get_interface_ipv4_subnet

INTERFACE_GUID = "{DEADC0FF-EEEE-4444-8888-2BF6900CBFA0}"
PCAP_INTERFACE = rf"\Device\NPF_{INTERFACE_GUID}"

IpAddress = Union[str, tuple[str, int, int]]


def create_adapter(
    *,
    name: str,
    nice_name: str,
    addresses: list[tuple[IpAddress, int]],
) -> SimpleNamespace:
    """Create an adapter mock with the configured IP addresses.

    Args:
        name: Adapter name.
        nice_name: Adapter friendly name.
        addresses: List of tuples containing the IP address and network prefix.

    Returns:
        A SimpleNamespace representing the adapter.
    """
    return SimpleNamespace(
        name=name,
        nice_name=nice_name,
        ips=[
            SimpleNamespace(
                ip=address,
                network_prefix=prefix,
            )
            for address, prefix in addresses
        ],
    )


def test_get_interface_ipv4_subnet_matches_pcap_guid(mocker) -> None:
    """Resolve a Windows Pcap path using its adapter GUID."""
    adapter = create_adapter(
        name=INTERFACE_GUID,
        nice_name="Ethernet",
        addresses=[("192.168.2.10", 24)],
    )
    mocker.patch(
        "ingenialink.ethernet.interface.ifaddr.get_adapters",
        return_value=[adapter],
    )

    subnet = get_interface_ipv4_subnet(PCAP_INTERFACE)

    assert subnet == ipaddress.IPv4Network("192.168.2.0/24")


def test_get_interface_ipv4_subnet_matches_system_name(mocker) -> None:
    """Resolve an adapter using its system interface name."""
    adapter = create_adapter(
        name="eth0",
        nice_name="eth0",
        addresses=[("10.0.0.25", 16)],
    )
    mocker.patch(
        "ingenialink.ethernet.interface.ifaddr.get_adapters",
        return_value=[adapter],
    )

    subnet = get_interface_ipv4_subnet("eth0")

    assert subnet == ipaddress.IPv4Network("10.0.0.0/16")


def test_get_interface_ipv4_subnet_matches_friendly_name(mocker) -> None:
    """Resolve an adapter using its friendly name."""
    adapter = create_adapter(
        name=INTERFACE_GUID,
        nice_name="Ethernet",
        addresses=[("172.16.1.10", 24)],
    )
    mocker.patch(
        "ingenialink.ethernet.interface.ifaddr.get_adapters",
        return_value=[adapter],
    )

    subnet = get_interface_ipv4_subnet("Ethernet")

    assert subnet == ipaddress.IPv4Network("172.16.1.0/24")


def test_get_interface_ipv4_subnet_ignores_ipv6_addresses(mocker) -> None:
    """Ignore IPv6 addresses when resolving the IPv4 subnet."""
    adapter = create_adapter(
        name="eth0",
        nice_name="eth0",
        addresses=[
            (("fe80::1", 0, 2), 64),
            ("192.168.1.20", 24),
        ],
    )
    mocker.patch(
        "ingenialink.ethernet.interface.ifaddr.get_adapters",
        return_value=[adapter],
    )

    subnet = get_interface_ipv4_subnet("eth0")

    assert subnet == ipaddress.IPv4Network("192.168.1.0/24")


def test_get_interface_ipv4_subnet_raises_if_interface_has_no_ipv4(
    mocker,
) -> None:
    """Raise an error when the interface has no IPv4 address."""
    adapter = create_adapter(
        name="eth0",
        nice_name="eth0",
        addresses=[(("fe80::1", 0, 2), 64)],
    )
    mocker.patch(
        "ingenialink.ethernet.interface.ifaddr.get_adapters",
        return_value=[adapter],
    )

    with pytest.raises(
        OSError,
        match="has no configured IPv4 address",
    ):
        get_interface_ipv4_subnet("eth0")


def test_get_interface_ipv4_subnet_raises_if_interface_is_missing(
    mocker,
) -> None:
    """Raise an error when the interface cannot be found."""
    mocker.patch(
        "ingenialink.ethernet.interface.ifaddr.get_adapters",
        return_value=[],
    )

    with pytest.raises(
        OSError,
        match="could not be found",
    ):
        get_interface_ipv4_subnet("missing-interface")
