"""Tests for the client-side virtual SDCP servo."""

from unittest.mock import MagicMock, patch

from ingenialink.ethernet.tsn.sdcp.connection import SDCPConnection
from ingenialink.virtual.sdcp.servo import VIRTUAL_SDCP_INTERFACE, VirtualSDCPServo

DICTIONARY_PATH = "test_dictionary.xdf"
TARGET = "::1"
TIMEOUT_S = 2.0


def test_virtual_servo_creates_loopback_connection() -> None:
    """Create an SDCP connection using the loopback interface placeholder."""
    connection_mock = MagicMock(spec=SDCPConnection)

    with (
        patch(
            "ingenialink.ethernet.tsn.sdcp.servo.SDCPConnection",
            return_value=connection_mock,
        ) as connection_class_mock,
        patch(
            "ingenialink.ethernet.tsn.sdcp.servo.Servo.__init__",
            return_value=None,
        ),
    ):
        servo = VirtualSDCPServo(
            target=TARGET,
            dictionary_path=DICTIONARY_PATH,
            connection_timeout=TIMEOUT_S,
        )

    assert servo._connection is connection_mock
    connection_class_mock.assert_called_once_with(TARGET, VIRTUAL_SDCP_INTERFACE, TIMEOUT_S)

    servo._disconnect_event_publisher = MagicMock()
    servo.disconnect()

    connection_mock.close.assert_called_once_with()
