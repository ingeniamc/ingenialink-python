import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ingenialink.ethernet.servo import EthernetServo
from ingenialink.exceptions import ILIOError, ILRegisterAccessError


class TestILRegisterAccessError:
    """Tests for the ILRegisterAccessError exception class."""

    def test_is_subclass_of_ilioerror(self) -> None:
        assert issubclass(ILRegisterAccessError, ILIOError)

    def test_attributes_are_stored(self) -> None:
        reg = SimpleNamespace(identifier="MY_REG")
        cause = ValueError("low-level failure")
        root_cause = "Abort code 0x06090011"

        error = ILRegisterAccessError(
            base_message="Error reading MY_REG",
            reg=reg,
            base_exception=cause,
            reason=root_cause,
        )

        assert str(error) == "Error reading MY_REG. Abort code 0x06090011"
        assert error.reg is reg
        assert error.base_exception is cause
        assert error.reason == root_cause

    def test_can_be_caught_as_ilioerror(self) -> None:
        reg = SimpleNamespace(identifier="MY_REG")
        cause = RuntimeError("some io failure")

        with pytest.raises(ILIOError):
            raise ILRegisterAccessError(
                base_message="Error writing MY_REG",
                reg=reg,
                base_exception=cause,
                reason=str(cause),
            )


class TestEthernetRawReadWriteRaisesILRegisterAccessError:
    """Tests that EthernetServo._write_raw and _read_raw raise ILRegisterAccessError."""

    ETH_REGISTER = SimpleNamespace(
        identifier="DRV_DIAG_SYS_STATUS",
        address=0x0302,
        subnode=0,
    )

    class _ServoForRawIO(EthernetServo):
        def __init__(self) -> None:
            self._lock = threading.Lock()
            self.socket = MagicMock()

    def test_write_raw_raises_il_register_access_error_on_send_failure(self) -> None:
        servo = self._ServoForRawIO()
        servo.socket.sendall.side_effect = OSError("Network unreachable")

        with pytest.raises(ILRegisterAccessError) as exc_info:
            servo._write_raw(self.ETH_REGISTER, b"\x00\x00")

        error = exc_info.value
        assert error.reg is self.ETH_REGISTER
        assert isinstance(error.base_exception, ILIOError)
        assert error.base_message == f"Error writing {self.ETH_REGISTER.identifier}"
        assert error.reason == "Error sending data."
        assert str(error) == f"Error writing {self.ETH_REGISTER.identifier}. Error sending data."

    def test_read_raw_raises_il_register_access_error_on_send_failure(self) -> None:
        servo = self._ServoForRawIO()
        servo.socket.sendall.side_effect = OSError("Network unreachable")

        with pytest.raises(ILRegisterAccessError) as exc_info:
            servo._read_raw(self.ETH_REGISTER)

        error = exc_info.value
        assert error.reg is self.ETH_REGISTER
        assert isinstance(error.base_exception, ILIOError)
        assert error.base_message == f"Error reading {self.ETH_REGISTER.identifier}"
        assert error.reason == "Error sending data."
        assert str(error) == f"Error reading {self.ETH_REGISTER.identifier}. Error sending data."
