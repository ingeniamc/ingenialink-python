"""Servo access over the SDCP protocol."""

from abc import ABC
from typing import Any, Callable, Optional

from ingenialink.canopen.register import CanopenRegister
from ingenialink.dictionary import Interface
from ingenialink.exceptions import ILIOError
from ingenialink.servo import Servo

from .connection import SDCPConnection
from .sdcp import (
    SDCPErrorResponse,
    SDCPReadRequest,
    SDCPReadResponse,
    SDCPWriteRequest,
    SDCPWriteResponse,
)


class TSNServoBase(Servo, ABC):
    """Declaration of the base TSN servo behavior."""


class TSNServo(TSNServoBase):
    """TSN Servo instance.

    Args:
        target: IPv6 address of the SDCP device.
        interface: Network interface in the same format as
            :func:`ingenialink.ethernet.tsn.ipv6_discovery.discover_ipv6_devices`.
        dictionary_path: Path to the dictionary.
        connection_timeout: Timeout in seconds for SDCP requests and responses.
        servo_status_listener: Toggle the listener of the servo for
            its status, errors, faults, etc.
        disconnect_callback: Callback function to be called when the servo is disconnected.

    """

    _CONNECTION_TIMEOUT_S = 1.0
    interface = Interface.CAN
    _INITIAL_TRANSACTION_ID = 0x0000
    _MAX_TRANSACTION_ID = 0xFFFF

    def __init__(
        self,
        target: str,
        interface: str,
        dictionary_path: str,
        connection_timeout: float = _CONNECTION_TIMEOUT_S,
        servo_status_listener: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ) -> None:
        super().__init__(
            target, dictionary_path, servo_status_listener, disconnect_callback=disconnect_callback
        )
        self._connection = SDCPConnection(target, interface, connection_timeout)
        self._transaction_id = self._INITIAL_TRANSACTION_ID

    def _write_raw(self, reg: CanopenRegister, data: bytes, **_kwargs: Any) -> None:  # type: ignore [override]
        """Write raw register bytes through SDCP."""
        request = SDCPWriteRequest(self._next_transaction_id(), reg.idx, reg.subidx, data)
        response = self._connection.request(request)
        if isinstance(response, SDCPErrorResponse):
            raise self._sdcp_error("write", response)
        if not isinstance(response, SDCPWriteResponse):
            raise self._unexpected_response_error("write", response)

    def _read_raw(self, reg: CanopenRegister, **_kwargs: Any) -> bytes:  # type: ignore [override]
        """Read raw register bytes through SDCP.

        Returns:
            Raw register bytes.
        """
        request = SDCPReadRequest(self._next_transaction_id(), reg.idx, reg.subidx)
        response = self._connection.request(request)
        if isinstance(response, SDCPErrorResponse):
            raise self._sdcp_error("read", response)
        if not isinstance(response, SDCPReadResponse):
            raise self._unexpected_response_error("read", response)
        return response.value

    @staticmethod
    def _sdcp_error(operation: str, response: SDCPErrorResponse) -> ILIOError:
        return ILIOError(f"SDCP {operation} failed with error code 0x{response.error_code:08X}")

    @staticmethod
    def _unexpected_response_error(operation: str, response: object) -> ILIOError:
        return ILIOError(f"Unexpected SDCP {operation} response: {type(response).__name__}")

    def _next_transaction_id(self) -> int:
        """Return the next transaction ID for SDCP requests."""
        transaction_id = self._transaction_id
        self._transaction_id = (transaction_id + 1) & self._MAX_TRANSACTION_ID
        return transaction_id
