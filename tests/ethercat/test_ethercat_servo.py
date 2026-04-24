import contextlib
import threading
from types import SimpleNamespace
from typing import Optional
from unittest.mock import MagicMock

with contextlib.suppress(ImportError):
    import pysoem
import pytest

from ingenialink.ethercat.servo import EthercatServo, SdoOperationMsg
from ingenialink.exceptions import ILError, ILIOError, ILRegisterAccessError

REGISTER = SimpleNamespace(idx=0x2010, subidx=0x00, identifier="DRV_STATE_STATUS")


def _make_wkc_error(wkc: int) -> pysoem.WkcError:
    """Create a pysoem.WkcError with the given working counter value.

    Returns:
        A WkcError with the specified wkc.
    """
    err = pysoem.WkcError.__new__(pysoem.WkcError)
    err.wkc = wkc
    return err


class _ServoForRawIO(EthercatServo):
    """Minimal EthercatServo subclass that bypasses full __init__."""

    def __init__(self, slave: object, sdo_read_write_release_gil: Optional[bool] = None) -> None:
        self._EthercatServo__slave = slave
        self._EthercatServo__sdo_read_write_release_gil = sdo_read_write_release_gil
        self._EthercatServo__emcy_observers = []
        self._lock = threading.Lock()


class TestHandleSdoException:
    """Tests that _handle_sdo_exception raises ILRegisterAccessError for each pysoem error type."""

    @staticmethod
    def _build_servo() -> _ServoForRawIO:
        return _ServoForRawIO(MagicMock())

    @pytest.mark.parametrize(
        ("wkc", "expected_reason"),
        [
            (EthercatServo.NO_RESPONSE_WORKING_COUNTER, "The working counter remained unchanged"),
            (EthercatServo.TIMEOUT_WORKING_COUNTER, "Timeout"),
            (EthercatServo.NOFRAME_WORKING_COUNTER, "No frame"),
            (EthercatServo.UNKNOWN_FRAME_WORKING_COUNTER, "Unknown frame received"),
            (42, "Working counter: 42"),
        ],
        ids=["no_response", "timeout", "noframe", "unknown_frame", "unknown_code"],
    )
    def test_wkc_error_reason(self, wkc: int, expected_reason: str) -> None:
        """Each WKC error code produces the correct human-readable reason."""
        servo = self._build_servo()
        exc = _make_wkc_error(wkc)

        with pytest.raises(ILRegisterAccessError) as exc_info:
            servo._handle_sdo_exception(REGISTER, SdoOperationMsg.READ, exc)

        error = exc_info.value
        assert error.reg is REGISTER
        assert error.base_exception is exc
        assert error.reason == expected_reason

    @pytest.mark.parametrize(
        ("exception", "expected_fragments"),
        [
            (
                pysoem.SdoError(0, 1, 2, 0x06090011, "Sub index does not exist"),
                ["SdoError", "Abort code", "Sub index does not exist"],
            ),
            (
                pysoem.MailboxError(1, 2, "Mailbox timeout"),
                ["MailboxError", "Error code", "Mailbox timeout"],
            ),
            (
                pysoem.PacketError(1, 3),
                ["PacketError", "Error code", "Data container too small for type"],
            ),
        ],
        ids=["sdo_error", "mailbox_error", "packet_error"],
    )
    def test_protocol_error_reason(
        self, exception: Exception, expected_fragments: list[str]
    ) -> None:
        """SdoError, MailboxError, and PacketError produce reason strings with the right details."""
        servo = self._build_servo()

        with pytest.raises(ILRegisterAccessError) as exc_info:
            servo._handle_sdo_exception(REGISTER, SdoOperationMsg.READ, exception)

        error = exc_info.value
        assert error.reg is REGISTER
        assert error.base_exception is exception
        for fragment in expected_fragments:
            assert fragment in error.reason

    def test_generic_exception_uses_str(self) -> None:
        """Non-pysoem exceptions fall back to str(exception) as the reason."""
        servo = self._build_servo()
        exc = ILIOError("Some IO error")

        with pytest.raises(ILRegisterAccessError) as exc_info:
            servo._handle_sdo_exception(REGISTER, SdoOperationMsg.READ, exc)

        assert exc_info.value.reason == "Some IO error"


class TestReadRawWriteRawErrorHandling:
    """Tests that _read_raw and _write_raw properly translate exceptions."""

    @staticmethod
    def _build_servo_with_sdo_error(error: Exception, method: str) -> _ServoForRawIO:
        slave = MagicMock()
        getattr(slave, method).side_effect = error
        return _ServoForRawIO(slave)

    @pytest.mark.parametrize(
        ("sdo_method", "call_method", "call_args", "expected_word"),
        [
            ("sdo_read", "_read_raw", (REGISTER,), "reading"),
            ("sdo_write", "_write_raw", (REGISTER, b"\x00\x00"), "writing"),
        ],
        ids=["read", "write"],
    )
    def test_sdo_error_raises_il_register_access_error(
        self, sdo_method: str, call_method: str, call_args: tuple, expected_word: str
    ) -> None:
        """pysoem.SdoError during read/write is wrapped in ILRegisterAccessError."""
        exc = pysoem.SdoError(0, 1, 2, 0x06090011, "Sub index does not exist")
        servo = self._build_servo_with_sdo_error(exc, sdo_method)

        with pytest.raises(ILRegisterAccessError) as exc_info:
            getattr(servo, call_method)(*call_args)

        error = exc_info.value
        assert error.reg is REGISTER
        assert error.base_exception is exc
        assert expected_word in error.base_message

    @pytest.mark.parametrize(
        ("sdo_method", "call_method", "call_args", "wkc", "expected_reason"),
        [
            ("sdo_read", "_read_raw", (REGISTER,), 0, "The working counter remained unchanged"),
            ("sdo_write", "_write_raw", (REGISTER, b"\x00\x00"), -5, "Timeout"),
        ],
        ids=["read_wkc", "write_wkc"],
    )
    def test_wkc_error_raises_il_register_access_error(
        self,
        sdo_method: str,
        call_method: str,
        call_args: tuple,
        wkc: int,
        expected_reason: str,
    ) -> None:
        """pysoem.WkcError during read/write is wrapped in ILRegisterAccessError."""
        exc = _make_wkc_error(wkc)
        servo = self._build_servo_with_sdo_error(exc, sdo_method)

        with pytest.raises(ILRegisterAccessError) as exc_info:
            getattr(servo, call_method)(*call_args)

        assert expected_reason in exc_info.value.reason

    @pytest.mark.parametrize(
        ("sdo_method", "call_method", "call_args", "exception"),
        [
            ("sdo_read", "_read_raw", (REGISTER,), AttributeError("NoneType")),
            ("sdo_write", "_write_raw", (REGISTER, b"\x00\x00"), AttributeError("NoneType")),
            ("sdo_read", "_read_raw", (REGISTER,), ILError("Slave reference is not available.")),
            (
                "sdo_write",
                "_write_raw",
                (REGISTER, b"\x00\x00"),
                ILError("Slave reference is not available."),
            ),
        ],
        ids=["read_attribute_error", "write_attribute_error", "read_ilerror", "write_ilerror"],
    )
    def test_disconnect_errors_raise_ilioerror(
        self, sdo_method: str, call_method: str, call_args: tuple, exception: Exception
    ) -> None:
        """AttributeError and ILError during SDO operations are caught and re-raised
        as ILIOError with a disconnection message."""
        servo = self._build_servo_with_sdo_error(exception, sdo_method)

        with pytest.raises(ILIOError, match="drive has been disconnected") as exc_info:
            getattr(servo, call_method)(*call_args)

        assert exc_info.value.__cause__ is exception

    @pytest.mark.parametrize(
        ("sdo_method", "call_method", "call_args"),
        [
            ("sdo_read", "_read_raw", (REGISTER,)),
            ("sdo_write", "_write_raw", (REGISTER, b"\x00\x00")),
        ],
        ids=["read", "write"],
    )
    def test_ilioerror_routed_to_handle_sdo_exception(
        self, sdo_method: str, call_method: str, call_args: tuple
    ) -> None:
        """ILIOError is routed through _handle_sdo_exception, producing ILRegisterAccessError."""
        exc = ILIOError("Some IO failure")
        servo = self._build_servo_with_sdo_error(exc, sdo_method)

        with pytest.raises(ILRegisterAccessError) as exc_info:
            getattr(servo, call_method)(*call_args)

        assert exc_info.value.base_exception is exc
