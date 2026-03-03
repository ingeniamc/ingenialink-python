import socket
from typing import Any, Callable, Optional

from typing_extensions import override

from ingenialink import Servo
from ingenialink.dictionary import Interface
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.ethercat.servo import EthercatServoBase
from ingenialink.exceptions import ILIOError
from ingenialink.register import Register
from ingenialink.virtual.servo import VirtualServoBase


class VirtualEthercatServo(EthercatServoBase):
    """Virtual EtherCAT servo implementation using serialized object frames."""

    interface = Interface.ECAT

    def __init__(
        self,
        socket: socket.socket,
        slave_id: int,
        dictionary_path: str,
        servo_status_listener: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ) -> None:
        self.socket = socket
        self.slave_id = slave_id
        self.ip_address, self.port = self.socket.getpeername()
        super().__init__(
            self.slave_id,
            dictionary_path,
            servo_status_listener=False,
            disconnect_callback=disconnect_callback,
        )
        self._virtual_base = VirtualServoBase(self.socket, self._lock)
        if servo_status_listener:
            self.start_status_listener()

    def _read_raw(self, reg: Register, **kwargs: Any) -> bytes:
        _ = kwargs
        if not isinstance(reg, EthercatRegister):
            raise ILIOError(f"Expected EthercatRegister, got {type(reg)}")
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
        if not isinstance(reg, EthercatRegister):
            raise ILIOError(f"Expected EthercatRegister, got {type(reg)}")
        frame_data = {
            "command": "write",
            "index": reg.idx,
            "subindex": reg.subidx,
            "data": data,
        }
        response = self._virtual_base.exchange_sdo_frame(frame_data)
        self._virtual_base.deserialize_write_response(response)

    @override
    def check_servo_is_in_preoperational_state(self) -> None:
        pass
