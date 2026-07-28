"""Servo access over the SDCP protocol."""

from abc import ABC
from threading import Lock
from typing import Any, Callable, Optional

from ingenialink.canopen.register import CanopenRegister
from ingenialink.dictionary import Interface
from ingenialink.enums.register import ByteOrder
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

    _REGISTER_BYTE_ORDER: ByteOrder = ByteOrder.BIG


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

    # Temporary use of the CAN interface until TSN dictionary support is available (INGK-1279).
    interface = Interface.CAN

    _CONNECTION_TIMEOUT_S = 1.0
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
        self._request_lock = Lock()

    def _write_raw(self, reg: CanopenRegister, data: bytes, **_kwargs: Any) -> None:  # type: ignore [override]
        """Write raw register bytes through SDCP.

        Args:
            reg: Register to write.
            data: Raw register bytes to write.

        Raises:
            ILIOError: If the SDCP write fails or the response is unexpected.

        """
        with self._request_lock:
            request = SDCPWriteRequest(self._next_transaction_id(), reg.idx, reg.subidx, data)
            response = self._connection.request(request)
            if isinstance(response, SDCPErrorResponse):
                raise ILIOError(f"SDCP write failed with error code 0x{response.error_code:08X}")
            if not isinstance(response, SDCPWriteResponse):
                raise ILIOError(f"Unexpected SDCP write response: {response}")

    def _read_raw(self, reg: CanopenRegister, **_kwargs: Any) -> bytes:  # type: ignore [override]
        """Read raw register bytes through SDCP.

        Args:
            reg: Register to read.

        Returns:
            Raw register bytes.

        Raises:
            ILIOError: If the SDCP read fails or the response is unexpected.

        """
        with self._request_lock:
            request = SDCPReadRequest(self._next_transaction_id(), reg.idx, reg.subidx)
            response = self._connection.request(request)
            if isinstance(response, SDCPErrorResponse):
                raise ILIOError(f"SDCP read failed with error code 0x{response.error_code:08X}")
            if not isinstance(response, SDCPReadResponse):
                raise ILIOError(f"Unexpected SDCP read response: {response}")
            return response.value

    def _next_transaction_id(self) -> int:
        """Return the next transaction ID for SDCP requests."""
        transaction_id = self._transaction_id
        self._transaction_id = (transaction_id + 1) & self._MAX_TRANSACTION_ID
        return transaction_id
