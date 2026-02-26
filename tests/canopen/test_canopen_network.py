import platform
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from can.interfaces.pcan.pcan import PcanCanOperationError
from summit_testing_framework.setups import (
    MultiRackServiceConfigSpecifier,
    RackServiceConfigSpecifier,
)

from ingenialink.canopen.network import CanBaudrate, CanDevice, CanopenNetwork
from ingenialink.exceptions import ILError

if TYPE_CHECKING:
    from pytest import FixtureRequest
    from summit_testing_framework.setup_fixtures import ConnectionWrapper
    from summit_testing_framework.setups.descriptors import DriveCanOpenSetup

    from ingenialink.canopen.servo import CanopenServo

test_bus = "virtual"
test_baudrate = 1000000
test_channel = 0


def _raise_pcan_bus_off(*_args, **_kwargs) -> None:
    raise PcanCanOperationError("Bus error: the CAN controller is in bus-off state.")


def _configure_mocked_connection(net, connection, slaves=None):
    """Attach a mocked connection to a network instance for unit-style tests.

    Returns:
        The same network instance with connection and optional slave scan behavior patched.
    """

    def setup_connection() -> None:
        net._connection = connection

    net._setup_connection = setup_connection
    net._teardown_connection = lambda: None
    if slaves is not None:
        net.scan_slaves = lambda: slaves
    return net


@pytest.fixture
def virtual_network():
    net = CanopenNetwork(
        device=CanDevice(test_bus), channel=test_channel, baudrate=CanBaudrate(test_baudrate)
    )
    return net


def test_getters_canopen(virtual_network):
    assert virtual_network.device == test_bus
    assert virtual_network.channel == test_channel
    assert virtual_network.baudrate == test_baudrate
    assert virtual_network.network is None


@pytest.mark.canopen
def test_connect_to_slave(servo: "CanopenServo", net: "CanopenNetwork") -> None:
    assert len(net.servos) == 1
    fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
    assert fw_version is not None and fw_version != ""


@pytest.mark.canopen
def test_connect_to_slave_target_not_in_nodes(
    net: "CanopenNetwork", setup_descriptor: "DriveCanOpenSetup"
) -> None:
    with pytest.raises(ILError):
        net.connect_to_slave(target=1234, dictionary=setup_descriptor.dictionary)


def test_connect_to_slave_none_nodes(virtual_network):
    net = virtual_network
    with pytest.raises(ILError):
        net.connect_to_slave(target=1, dictionary="")


@pytest.mark.canopen
def test_scan_slaves(net: "CanopenNetwork") -> None:
    slaves = net.scan_slaves()
    assert len(slaves) > 0


@pytest.mark.parametrize("can_device", [CanDevice.PCAN, CanDevice.KVASER, CanDevice.IXXAT])
def test_scan_slaves_missing_drivers(can_device):
    net = CanopenNetwork(
        device=can_device,
        channel=0,
        baudrate=CanBaudrate.Baudrate_1M,
    )
    with pytest.raises(ILError) as exc_info:
        net.scan_slaves()
    assert (
        str(exc_info.value) == f"The {can_device.value.upper()} transceiver is not detected. "
        f"Make sure that it's connected and"
        " its drivers are installed."
    )


@pytest.mark.canopen
def test_scan_slaves_info(
    setup_specifier,
    setup_descriptor: "DriveCanOpenSetup",
    servo_with_reconnect: "ConnectionWrapper",
    request: "FixtureRequest",
) -> None:
    servo_with_reconnect.disconnect()
    net = servo_with_reconnect.get_net()

    slaves_info = net.scan_slaves_info()

    assert len(slaves_info) > 0
    assert setup_descriptor.node_id in slaves_info

    if isinstance(setup_specifier, (RackServiceConfigSpecifier, MultiRackServiceConfigSpecifier)):
        drive = request.getfixturevalue("get_drive_configuration_from_rack_service")
        assert slaves_info[setup_descriptor.node_id].product_code == drive.product_code


@pytest.mark.canopen
def test_disconnect_from_slave(
    setup_descriptor: "DriveCanOpenSetup", servo_with_reconnect: "ConnectionWrapper"
) -> None:
    servo_with_reconnect.disconnect()
    net = servo_with_reconnect.get_net()

    disconnected_servos = []

    def dummy_callback(servo):
        disconnected_servos.append(servo.target)

    servo = net.connect_to_slave(
        target=setup_descriptor.node_id,
        dictionary=setup_descriptor.dictionary,
        disconnect_callback=dummy_callback,
    )

    assert len(disconnected_servos) == 0
    assert len(net.servos) == 1
    net.disconnect_from_slave(servo)
    assert len(net.servos) == 0
    assert len(disconnected_servos) == 1
    assert disconnected_servos[0] == setup_descriptor.node_id


def test_setup_and_teardown_connection(virtual_network) -> None:
    if platform.system() != "Windows":
        pytest.skip("Only for window machines")
    assert virtual_network._connection is None
    virtual_network._setup_connection()
    assert virtual_network._connection is not None
    virtual_network._teardown_connection()
    assert virtual_network._connection is None


@pytest.mark.skip
def test_load_firmware(
    servo: "CanopenServo", net: "CanopenNetwork", setup_descriptor: "DriveCanOpenSetup"
) -> None:
    assert len(net.servos) == 1
    fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")

    net.load_firmware(setup_descriptor.node_id, setup_descriptor.fw_data.fw_file)
    new_fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")

    assert new_fw_version != fw_version
    net.disconnect_from_slave(servo)


@pytest.mark.canopen
def test_recover_from_disconnection(net: "CanopenNetwork", servo: "CanopenServo", caplog) -> None:
    """Test that recover_from_disconnection properly resets the CANopen network.

    This test uses a real CANopen drive and verifies that the recover_from_disconnection
    method successfully calls _reset_connection() to re-establish communication.
    """
    assert servo is not None
    assert len(net.servos) == 1
    assert net._connection is not None

    # Read the firmware version to ensure communication is working
    fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
    assert fw_version is not None and fw_version != ""

    # Call recover_from_disconnection and verify it succeeds
    with caplog.at_level("INFO"):
        result = net.recover_from_disconnection()
        assert result is True, "recover_from_disconnection should successfully reset connection"
        assert "CANopen communication recovered." in caplog.text, (
            "Should log recovery success message"
        )

    # Verify connection is still established after recovery
    assert net._connection is not None
    assert len(net.servos) == 1

    # Verify we can still communicate with the servo after recovery
    new_fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
    assert new_fw_version == fw_version, "Firmware version should remain the same after recovery"


def test_scan_slaves_info_handles_bus_off_with_empty_slave_info(virtual_network) -> None:
    """scan_slaves_info should not raise on PCAN bus-off and should reset the bus."""
    # Arrange: one discovered slave whose SDO upload always fails with bus-off.
    reset_bus = Mock()

    bus = SimpleNamespace(reset=reset_bus)
    sdo = SimpleNamespace(upload=_raise_pcan_bus_off)
    node = SimpleNamespace(sdo=sdo)
    connection = SimpleNamespace(bus=bus, add_node=lambda _node_id: node)
    net = _configure_mocked_connection(virtual_network, connection, slaves=[1])

    # Act
    slaves_info = net.scan_slaves_info()

    # Assert: the failure is handled, slave entry is present, and bus reset is attempted.
    assert 1 in slaves_info
    assert slaves_info[1].product_code is None
    assert slaves_info[1].revision_number is None
    reset_bus.assert_called_once_with()


def test_scan_slaves_handles_pcan_bus_off(virtual_network) -> None:
    """scan_slaves should recover from scanner bus-off by resetting the bus."""
    # Arrange: scanner.search raises bus-off on an otherwise valid connection.
    net = virtual_network
    reset_bus = Mock()

    net.get_available_devices = lambda: [(net.device, net.channel)]  # type: ignore[method-assign]
    net._connection = SimpleNamespace(
        scanner=SimpleNamespace(reset=lambda: None, search=_raise_pcan_bus_off, nodes=[]),
        bus=SimpleNamespace(reset=reset_bus),
    )

    # Act
    nodes = net.scan_slaves()

    # Assert: scan returns empty result and bus reset is called once.
    assert nodes == []
    reset_bus.assert_called_once_with()


def test_connect_to_slave_handles_pcan_bus_off_as_ilerror(virtual_network) -> None:
    """connect_to_slave should translate low-level PCAN errors into ILError."""
    # Arrange: adding the node fails with a PCAN bus-off runtime error.
    connection = SimpleNamespace(add_node=_raise_pcan_bus_off)
    net = _configure_mocked_connection(virtual_network, connection, slaves=[1])

    # Act / Assert: API exposes a controlled library error.
    with pytest.raises(ILError) as exc_info:
        net.connect_to_slave(target=1, dictionary="dummy.xdf")

    assert str(exc_info.value) == (
        "Failed connecting to node 1. Please check the connection settings and verify the "
        "transceiver is properly connected."
    )


def test_teardown_connection_handles_pcan_bus_off(virtual_network) -> None:
    """_teardown_connection should swallow PCAN bus-off and always clear the connection."""
    # Arrange: disconnect itself fails with bus-off.
    net = virtual_network
    net._connection = SimpleNamespace(disconnect=_raise_pcan_bus_off)

    # Act
    net._teardown_connection()

    # Assert: teardown remains safe and always clears the connection object.
    assert net._connection is None
