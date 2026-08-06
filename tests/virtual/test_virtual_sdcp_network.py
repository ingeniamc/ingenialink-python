"""Tests for the client-side virtual SDCP network."""

from unittest.mock import MagicMock

import pytest

from ingenialink.ethernet.network import NetStatusListener
from ingenialink.network import NetDevEvt, NetState
from ingenialink.virtual.sdcp.network import VIRTUAL_SDCP_TARGET, VirtualSDCPNetwork
from ingenialink.virtual.sdcp.servo import VirtualSDCPServo

DICTIONARY_PATH = "test_dictionary.xdf"
TIMEOUT_S = 2.0


class ServoDouble(VirtualSDCPServo):
    """Concrete servo double that preserves the virtual servo type contract."""

    def __init__(self, **kwargs) -> None:
        self.target = kwargs["target"]
        self.stop_status_listener = MagicMock()
        self.disconnect = MagicMock()


@pytest.fixture
def network() -> VirtualSDCPNetwork:
    """Return a virtual SDCP network."""
    return VirtualSDCPNetwork()


def test_connect_to_slave_uses_loopback_target(
    network: VirtualSDCPNetwork,
    mocker,
) -> None:
    """Create the virtual servo with the known loopback target."""
    servo_mock = MagicMock(spec=VirtualSDCPServo)
    servo_mock.target = VIRTUAL_SDCP_TARGET
    servo_class_mock = mocker.patch(
        "ingenialink.virtual.sdcp.network.VirtualSDCPServo",
        return_value=servo_mock,
    )

    servo = network.connect_to_slave(
        dictionary=DICTIONARY_PATH,
        connection_timeout=TIMEOUT_S,
    )

    assert servo is servo_mock
    assert network.servos == [servo_mock]
    assert network.get_servo_state(servo) == NetState.CONNECTED
    servo_class_mock.assert_called_once_with(
        target=VIRTUAL_SDCP_TARGET,
        dictionary_path=DICTIONARY_PATH,
        connection_timeout=TIMEOUT_S,
        servo_status_listener=False,
        disconnect_callback=None,
    )


def test_connect_to_slave_starts_network_status_listener(
    network: VirtualSDCPNetwork,
    mocker,
) -> None:
    """Start the network listener when requested by the caller."""
    servo_mock = MagicMock(spec=VirtualSDCPServo)
    servo_mock.target = VIRTUAL_SDCP_TARGET
    mocker.patch(
        "ingenialink.virtual.sdcp.network.VirtualSDCPServo",
        return_value=servo_mock,
    )
    start_listener_mock = mocker.patch.object(network, "start_status_listener")

    network.connect_to_slave(
        dictionary=DICTIONARY_PATH,
        net_status_listener=True,
    )

    start_listener_mock.assert_called_once_with()


def test_network_status_listener_tracks_virtual_sdcp_connection_state(
    network: VirtualSDCPNetwork,
    mocker,
) -> None:
    """Publish network events when the virtual SDCP servo disappears and returns."""
    servo_mock = ServoDouble(target=VIRTUAL_SDCP_TARGET)
    servo_mock.is_alive = MagicMock(side_effect=[False, True])
    servo_mock._net_state_publisher = MagicMock()
    network.servos.append(servo_mock)
    network._set_servo_state(servo_mock, NetState.CONNECTED)

    listener = NetStatusListener(network)
    listener.process()
    listener.process()

    assert network.get_servo_state(servo_mock) == NetState.CONNECTED
    assert servo_mock._net_state_publisher.notify.call_args_list == [
        mocker.call(NetDevEvt.REMOVED),
        mocker.call(NetDevEvt.ADDED),
    ]


def test_disconnects_virtual_servo(
    network: VirtualSDCPNetwork,
    mocker,
) -> None:
    """Disconnect the virtual servo through the network."""
    mocker.patch("ingenialink.virtual.sdcp.network.VirtualSDCPServo", ServoDouble)
    servo = network.connect_to_slave(DICTIONARY_PATH)

    network.disconnect_from_slave(servo)

    assert servo.target == VIRTUAL_SDCP_TARGET
    servo.stop_status_listener.assert_called_once_with()
    servo.disconnect.assert_called_once_with()
    assert network.servos == []
    assert network.get_servo_state(servo) == NetState.DISCONNECTED
