"""Tests for SDCP node management in the Ethernet network."""

import pytest

from ingenialink.enums.node import NodeMode
from ingenialink.ethernet.network import EthernetNetwork, NetStatusListener
from ingenialink.ethernet.tsn.sdcp.discovery import SDCPNodeDiscovery
from ingenialink.ethernet.tsn.sdcp.node import SDCPNode
from ingenialink.ethernet.tsn.sdcp.servo import SDCPServo
from ingenialink.exceptions import ILError
from ingenialink.network import NetDevEvt, NetState

TARGET = "fe80::1"
UPDATED_TARGET = "fe80::2"
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


@pytest.fixture
def servo_mock(mocker) -> SDCPServo:
    """Return an SDCP servo mock with the required instance attributes."""
    servo = mocker.MagicMock(spec=SDCPServo)
    servo.target = TARGET
    servo._net_state_publisher = mocker.Mock()
    return servo


@pytest.fixture
def managed_node(
    discovery: SDCPNodeDiscovery,
    mocker,
) -> tuple[EthernetNetwork, SDCPNode]:
    """Return a network and an SDCP node managed by it."""
    network = EthernetNetwork(interface=INTERFACE)

    mocker.patch(
        "ingenialink.ethernet.network.discover_ipv6_devices",
        return_value=[TARGET],
    )
    mocker.patch(
        "ingenialink.ethernet.network.identify_sdcp_node",
        return_value=discovery,
    )

    node = network.scan_sdcp_nodes()[0]

    return network, node


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
        target=TARGET,
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
    assert node.target == TARGET
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
        return_value=[UPDATED_TARGET, TARGET],
    )

    nodes = network.scan_sdcp_nodes(timeout=TIMEOUT_S)

    assert len(nodes) == 1
    assert nodes[0].target == TARGET
    assert network.sdcp_nodes == nodes
    assert identify_mock.call_count == 2


def test_connect_to_node_rejects_unmanaged_node(
    discovery: SDCPNodeDiscovery,
    mocker,
) -> None:
    """Reject an SDCP node that does not belong to the network."""
    network = EthernetNetwork(interface=INTERFACE)
    node = SDCPNode(discovery)

    with pytest.raises(
        ValueError,
        match="The SDCP node is not managed by this network",
    ):
        network.connect_to_node(
            node=node,
            dictionary=mocker.sentinel.dictionary,
        )


def test_connect_to_node_connects_and_registers_servo(
    managed_node: tuple[EthernetNetwork, SDCPNode],
    servo_mock,
    mocker,
) -> None:
    """Connect through the node and register the returned servo."""
    network, node = managed_node
    disconnect_callback = mocker.Mock()
    dictionary = mocker.sentinel.dictionary

    connect_mock = mocker.patch.object(
        node,
        "connect",
        return_value=servo_mock,
    )

    servo = network.connect_to_node(
        node=node,
        dictionary=dictionary,
        servo_status_listener=True,
        disconnect_callback=disconnect_callback,
        connection_timeout=TIMEOUT_S,
    )

    assert servo is servo_mock
    assert network.servos == [servo_mock]
    assert network.get_servo_state(servo) == NetState.CONNECTED

    connect_mock.assert_called_once_with(
        dictionary_path=dictionary,
        servo_status_listener=True,
        disconnect_callback=disconnect_callback,
        connection_timeout=TIMEOUT_S,
    )


def test_disconnect_from_node_disconnects_and_unregisters_servo(
    managed_node: tuple[EthernetNetwork, SDCPNode],
    servo_mock,
    mocker,
) -> None:
    """Disconnect a managed SDCP node and unregister its servo."""
    network, node = managed_node

    mocker.patch(
        "ingenialink.ethernet.tsn.sdcp.node.SDCPServo",
        return_value=servo_mock,
    )

    servo = network.connect_to_node(
        node=node,
        dictionary=mocker.sentinel.dictionary,
    )

    assert network.get_servo_state(servo) == NetState.CONNECTED

    network.disconnect_from_node(node)

    servo_mock.stop_status_listener.assert_called_once_with()
    servo_mock.disconnect.assert_called_once_with()
    assert node.servo is None
    assert network.servos == []
    assert network.get_servo_state(servo) == NetState.DISCONNECTED


def test_disconnect_from_node_preserves_associations_on_failure(
    managed_node: tuple[EthernetNetwork, SDCPNode],
    servo_mock,
    mocker,
) -> None:
    """Preserve node and network associations if disconnection fails."""
    network, node = managed_node
    servo_mock.disconnect.side_effect = ILError("Disconnection failed")

    mocker.patch(
        "ingenialink.ethernet.tsn.sdcp.node.SDCPServo",
        return_value=servo_mock,
    )

    servo = network.connect_to_node(
        node=node,
        dictionary=mocker.sentinel.dictionary,
    )

    assert network.get_servo_state(servo) == NetState.CONNECTED

    with pytest.raises(ILError, match="Disconnection failed"):
        network.disconnect_from_node(node)

    servo_mock.stop_status_listener.assert_called_once_with()
    assert node.servo is servo
    assert network.servos == [servo]
    assert network.get_servo_state(servo) == NetState.CONNECTED


def test_disconnect_from_node_rejects_unmanaged_node(
    discovery: SDCPNodeDiscovery,
) -> None:
    """Reject disconnection of an unmanaged SDCP node."""
    network = EthernetNetwork(interface=INTERFACE)
    node = SDCPNode(discovery)

    with pytest.raises(
        ValueError,
        match="The SDCP node is not managed by this network",
    ):
        network.disconnect_from_node(node)


def test_disconnect_from_node_rejects_unconnected_node(
    managed_node: tuple[EthernetNetwork, SDCPNode],
) -> None:
    """Reject disconnection of a managed node that is not connected."""
    network, node = managed_node

    with pytest.raises(
        ValueError,
        match="The SDCP node is not connected through this network",
    ):
        network.disconnect_from_node(node)


def test_net_status_listener_tracks_sdcp_connection_state(
    managed_node: tuple[EthernetNetwork, SDCPNode],
    servo_mock,
    mocker,
) -> None:
    """Track SDCP servo disconnection and reconnection."""
    network, node = managed_node
    servo_mock.is_alive.side_effect = [False, True, True]

    mocker.patch.object(
        node,
        "connect",
        return_value=servo_mock,
    )

    servo = network.connect_to_node(
        node=node,
        dictionary=mocker.sentinel.dictionary,
    )

    listener = NetStatusListener(network)

    listener.process()

    assert network.get_servo_state(servo) == NetState.DISCONNECTED

    listener.process()

    assert network.get_servo_state(servo) == NetState.CONNECTED
    assert servo_mock._net_state_publisher.notify.call_args_list == [
        mocker.call(NetDevEvt.REMOVED),
        mocker.call(NetDevEvt.ADDED),
    ]


def test_connect_to_node_starts_net_status_listener(
    managed_node: tuple[EthernetNetwork, SDCPNode],
    servo_mock,
    mocker,
) -> None:
    """Start the network status listener when requested."""
    network, node = managed_node

    mocker.patch.object(
        node,
        "connect",
        return_value=servo_mock,
    )
    start_listener_mock = mocker.patch.object(
        network,
        "start_status_listener",
    )

    network.connect_to_node(
        node=node,
        dictionary=mocker.sentinel.dictionary,
        net_status_listener=True,
    )

    start_listener_mock.assert_called_once_with()
