"""Servo access over the SDCP protocol."""

from abc import ABC
from typing import Any, Callable, Optional

from ingenialink.canopen.register import CanopenRegister
from ingenialink.dictionary import Interface
from ingenialink.servo import Servo

from .connection import SDCPConnection
from .sdcp import (
    SDCPReadRequest,
    SDCPWriteRequest,
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
        self._transaction_id = 0x0

    def _write_raw(self, reg: CanopenRegister, data: bytes, **_kwargs: Any) -> None:  # type: ignore [override]
        """Write raw register bytes through SDCP."""
        request = SDCPWriteRequest(self._next_transaction_id(), reg.idx, reg.subidx, data)
        self._connection.request(request)

    def _read_raw(self, reg: CanopenRegister, **_kwargs: Any) -> bytes:  # type: ignore [override]
        """Read raw register bytes through SDCP.

        Returns:
            Raw register bytes.
        """
        request = SDCPReadRequest(self._next_transaction_id(), reg.idx, reg.subidx)
        response = self._connection.request(request)
        return bytes(response)

    def _next_transaction_id(self) -> int:
        """Return the next transaction ID for SDCP requests."""
        self._transaction_id += 1
        return self._transaction_id
