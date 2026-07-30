"""Tests for SDCP servo register access over UDP/IPv6."""

from unittest.mock import MagicMock, patch

import pytest

from ingenialink import RegAccess, RegDtype
from ingenialink.canopen.register import CanopenRegister
from ingenialink.ethernet.tsn.sdcp.messages import (
    SDCPReadRequest,
    SDCPReadResponse,
    SDCPReadResponseError,
    SDCPWriteRequest,
    SDCPWriteResponse,
    SDCPWriteResponseError,
)
from ingenialink.ethernet.tsn.sdcp.servo import SDCPServo
from ingenialink.ethernet.tsn.servo import TSNServoBase
from ingenialink.exceptions import ILIOError

TARGET = "fe80::1"
INTERFACE = "test-interface"
DICTIONARY_PATH = "test_dictionary.xdf"


@pytest.fixture
def connection_mock() -> MagicMock:
    """Return a mocked SDCP connection."""
    return MagicMock()


@pytest.fixture
def servo(connection_mock: MagicMock) -> SDCPServo:
    """Create an SDCP servo without loading a dictionary or opening a socket.

    Returns:
        SDCP servo with a mocked SDCP connection.
    """
    with (
        patch(
            "ingenialink.ethernet.tsn.sdcp.servo.Servo.__init__",
            return_value=None,
        ),
        patch(
            "ingenialink.ethernet.tsn.sdcp.servo.SDCPConnection",
            return_value=connection_mock,
        ),
    ):
        return SDCPServo(
            target=TARGET,
            interface=INTERFACE,
            dictionary_path=DICTIONARY_PATH,
        )


@pytest.fixture
def register() -> CanopenRegister:
    """Return a mocked unsigned 16-bit CANopen register."""
    register_mock = MagicMock(spec=CanopenRegister)
    register_mock.idx = 0x1000
    register_mock.subidx = 0x00
    register_mock.dtype = RegDtype.U16
    register_mock.access = RegAccess.RW
    register_mock.identifier = "TEST_REGISTER"
    return register_mock


def test_read_decodes_big_endian_value(
    servo: SDCPServo,
    register: CanopenRegister,
    connection_mock: MagicMock,
) -> None:
    """Build a Read request and decode its value as big-endian."""
    connection_mock.request.return_value = SDCPReadResponse(
        transaction_id=0x0000,
        value=b"\x12\x34",
    )

    with (
        patch.object(servo, "_get_reg", return_value=register),
        patch.object(servo, "_notify_register_update") as notify_mock,
    ):
        value = servo.read(register)

    assert value == 0x1234
    connection_mock.request.assert_called_once_with(
        SDCPReadRequest(
            transaction_id=0x0000,
            index=register.idx,
            subindex=register.subidx,
        )
    )
    notify_mock.assert_called_once_with(register, 0x1234)


def test_sdcp_servo_uses_tsn_base_class() -> None:
    """Use the shared TSN servo base for SDCP register access."""
    assert issubclass(SDCPServo, TSNServoBase)


def test_write_encodes_big_endian_value(
    servo: SDCPServo,
    register: CanopenRegister,
    connection_mock: MagicMock,
) -> None:
    """Encode a value as big-endian and send it in a Write request."""
    connection_mock.request.return_value = SDCPWriteResponse(
        transaction_id=0x0000,
    )

    with (
        patch.object(servo, "_get_reg", return_value=register),
        patch.object(servo, "_notify_register_update") as notify_mock,
    ):
        servo.write(register, 0x1234)

    connection_mock.request.assert_called_once_with(
        SDCPWriteRequest(
            transaction_id=0x0000,
            index=register.idx,
            subindex=register.subidx,
            value=b"\x12\x34",
        )
    )
    notify_mock.assert_called_once_with(register, 0x1234)


def test_write_preserves_explicit_bytes(
    servo: SDCPServo,
    register: CanopenRegister,
    connection_mock: MagicMock,
) -> None:
    """Send explicitly supplied raw bytes without changing their order."""
    connection_mock.request.return_value = SDCPWriteResponse(
        transaction_id=0x0000,
    )
    raw_value = b"\x34\x12"

    with (
        patch.object(servo, "_get_reg", return_value=register),
        patch.object(servo, "_notify_register_update") as notify_mock,
    ):
        servo.write(register, raw_value)

    connection_mock.request.assert_called_once_with(
        SDCPWriteRequest(
            transaction_id=0x0000,
            index=register.idx,
            subindex=register.subidx,
            value=raw_value,
        )
    )
    notify_mock.assert_called_once_with(register, raw_value)


def test_read_error_response_raises_il_io_error(
    servo: SDCPServo,
    register: CanopenRegister,
    connection_mock: MagicMock,
) -> None:
    """Convert an SDCP Read error response to ILIOError."""
    connection_mock.request.return_value = SDCPReadResponseError(
        transaction_id=0x0000,
        error_code=0xFFFF0001,
    )

    with pytest.raises(
        ILIOError,
        match="SDCP read failed with error code 0xFFFF0001",
    ):
        servo._read_raw(register)


def test_write_error_response_raises_il_io_error(
    servo: SDCPServo,
    register: CanopenRegister,
    connection_mock: MagicMock,
) -> None:
    """Convert an SDCP Write error response to ILIOError."""
    connection_mock.request.return_value = SDCPWriteResponseError(
        transaction_id=0x0000,
        error_code=0xFFFF0002,
    )

    with pytest.raises(
        ILIOError,
        match="SDCP write failed with error code 0xFFFF0002",
    ):
        servo._write_raw(register, b"\x12\x34")


def test_read_rejects_unexpected_response_type(
    servo: SDCPServo,
    register: CanopenRegister,
    connection_mock: MagicMock,
) -> None:
    """Reject a valid non-Read response for a Read request."""
    connection_mock.request.return_value = SDCPWriteResponse(
        transaction_id=0x0000,
    )

    with pytest.raises(
        ILIOError,
        match="Unexpected SDCP read response",
    ):
        servo._read_raw(register)


def test_write_rejects_unexpected_response_type(
    servo: SDCPServo,
    register: CanopenRegister,
    connection_mock: MagicMock,
) -> None:
    """Reject a valid non-Write response for a Write request."""
    connection_mock.request.return_value = SDCPReadResponse(
        transaction_id=0x0000,
        value=b"\x12\x34",
    )

    with pytest.raises(
        ILIOError,
        match="Unexpected SDCP write response",
    ):
        servo._write_raw(register, b"\x12\x34")


def test_transaction_id_increments(servo: SDCPServo) -> None:
    """Allocate transaction IDs sequentially from zero."""
    assert servo._next_transaction_id() == 0x0000
    assert servo._next_transaction_id() == 0x0001
    assert servo._next_transaction_id() == 0x0002


def test_transaction_id_wraps(servo: SDCPServo) -> None:
    """Wrap transaction IDs after the maximum 16-bit value."""
    servo._transaction_id = servo._MAX_TRANSACTION_ID

    assert servo._next_transaction_id() == 0xFFFF
    assert servo._next_transaction_id() == 0x0000
