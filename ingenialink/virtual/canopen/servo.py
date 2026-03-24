import socket
from typing import Any, Callable, Optional

from ingenialink import Servo
from ingenialink.canopen.register import CanopenRegister
from ingenialink.canopen.servo import CanopenServoBase
from ingenialink.dictionary import Interface
from ingenialink.exceptions import ILIOError
from ingenialink.register import Register
from ingenialink.virtual.servo import VirtualServoBase


class VirtualCanopenServo(CanopenServoBase):
    """Virtual CANopen servo implementation using serialized object frames."""

    interface = Interface.CAN

    def __init__(
        self,
        socket: socket.socket,
        target: int,
        dictionary_path: str,
        servo_status_listener: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ) -> None:
        self.socket = socket
        self.ip_address, self.port = self.socket.getpeername()
        super().__init__(
            target,
            dictionary_path,
            servo_status_listener=False,
            disconnect_callback=disconnect_callback,
        )
        self._virtual_base = VirtualServoBase(self.socket, self._lock)
        if servo_status_listener:
            self.start_status_listener()

    def _read_raw(self, reg: Register, **kwargs: Any) -> bytes:
        _ = kwargs
        if not isinstance(reg, CanopenRegister):
            raise ILIOError(f"Expected CanopenRegister, got {type(reg)}")
        frame_data = {
            "command": "read",
            "index": reg.idx,
            "subindex": reg.subidx,
        }
        response = self._virtual_base.exchange_sdo_frame(frame_data)
        return self._virtual_base.deserialize_read_response(response)

    def _write_raw(
        self,
        reg: Register,
        data: bytes,
        **kwargs: Any,
    ) -> None:
        _ = kwargs
        if not isinstance(reg, CanopenRegister):
            raise ILIOError(f"Expected CanopenRegister, got {type(reg)}")
        frame_data = {
            "command": "write",
            "index": reg.idx,
            "subindex": reg.subidx,
            "data": data,
        }
        response = self._virtual_base.exchange_sdo_frame(frame_data)
        self._virtual_base.deserialize_write_response(response)
