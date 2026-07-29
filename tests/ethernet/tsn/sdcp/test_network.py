"""Tests for SDCP node management in the Ethernet network."""

import pytest

from ingenialink.enums.node import NodeMode
from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.ethernet.tsn.sdcp.node import SDCPNode, SDCPNodeDiscovery
from ingenialink.exceptions import ILError

TARGET = "fe80::1"
INTERFACE = "test-interface"
TIMEOUT_S = 2.0

PROTOCOL_VERSION = 1
SERIAL_NUMBER = 0x12345678
PRODUCT_CODE = 0x90ABCDEF
REVISION_NUMBER = 0x00010002


@pytest.fixture
def discovery() -> SDCPNodeDiscovery:
    """Return representative SDCP node discovery information."""
    return SDCPNodeDiscovery(
        target=TARGET,
        interface=INTERFACE,
        protocol_version=PROTOCOL_VERSION,
        serial_number=SERIAL_NUMBER,
        product_code=PRODUCT_CODE,
        revision_number=REVISION_NUMBER,
        mode=NodeMode.APPLICATION,
    )


def test_scan_sdcp_nodes_requires_interface() -> None:
    """Require an interface for SDCP node discovery."""
    network = EthernetNetwork()

    with pytest.raises(
        ValueError,
        match="A network interface is required to scan SDCP nodes",
    ):
        network.scan_sdcp_nodes()


def test_scan_sdcp_nodes_creates_and_stores_node(
    discovery: SDCPNodeDiscovery,
    mocker,
) -> None:
    """Create and store a node for an identified SDCP device."""
    network = EthernetNetwork(interface=INTERFACE)

    discover_mock = mocker.patch(
        "ingenialink.ethernet.network.discover_ipv6_devices",
        return_value=[TARGET],
    )
    identify_mock = mocker.patch(
        "ingenialink.ethernet.network.identify_sdcp_node",
        return_value=discovery,
    )

    nodes = network.scan_sdcp_nodes(timeout=TIMEOUT_S)

    assert len(nodes) == 1
    assert isinstance(nodes[0], SDCPNode)
    assert network.sdcp_nodes == nodes
    assert network.interface == INTERFACE

    discover_mock.assert_called_once_with(INTERFACE)
    identify_mock.assert_called_once_with(
        target=TARGET,
        interface=INTERFACE,
        timeout=TIMEOUT_S,
    )


def test_scan_sdcp_nodes_updates_existing_node(
    discovery: SDCPNodeDiscovery,
    mocker,
) -> None:
    """Update a known node without replacing its instance."""
    network = EthernetNetwork(interface=INTERFACE)

    mocker.patch(
        "ingenialink.ethernet.network.discover_ipv6_devices",
        return_value=[TARGET],
    )
    identify_mock = mocker.patch(
        "ingenialink.ethernet.network.identify_sdcp_node",
        return_value=discovery,
    )

    node = network.scan_sdcp_nodes()[0]

    identify_mock.return_value = SDCPNodeDiscovery(
        target="fe80::2",
        interface=INTERFACE,
        protocol_version=PROTOCOL_VERSION + 1,
        serial_number=SERIAL_NUMBER,
        product_code=PRODUCT_CODE,
        revision_number=REVISION_NUMBER + 1,
        mode=NodeMode.APPLICATION,
    )

    nodes = network.scan_sdcp_nodes()

    assert nodes == [node]
    assert network.sdcp_nodes == [node]
    assert nodes[0] is node
    assert node.target == "fe80::2"
    assert node.protocol_version == PROTOCOL_VERSION + 1
    assert node.revision_number == REVISION_NUMBER + 1


def test_scan_sdcp_nodes_ignores_identification_errors(
    discovery: SDCPNodeDiscovery,
    mocker,
) -> None:
    """Ignore IPv6 devices that cannot be identified through SDCP."""
    network = EthernetNetwork(interface=INTERFACE)

    identify_mock = mocker.patch(
        "ingenialink.ethernet.network.identify_sdcp_node",
        side_effect=[
            ILError("Identification failed"),
            discovery,
        ],
    )
    mocker.patch(
        "ingenialink.ethernet.network.discover_ipv6_devices",
        return_value=["fe80::2", TARGET],
    )

    nodes = network.scan_sdcp_nodes(timeout=TIMEOUT_S)

    assert len(nodes) == 1
    assert nodes[0].target == TARGET
    assert network.sdcp_nodes == nodes
    assert identify_mock.call_count == 2
