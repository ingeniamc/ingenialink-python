import socket
from typing import Any, Callable, Optional

from ingenialink import Servo
from ingenialink.dictionary import Interface
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.exceptions import ILIOError
from ingenialink.register import Register
from ingenialink.servo import EthercatServoBase
from ingenialink.virtual.servo import VirtualServoBase


class VirtualEthercatServo(EthercatServoBase):
    """Virtual EtherCAT servo implementation using serialized object frames."""

    interface = Interface.VIRTUAL

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
            servo_status_listener,
            disconnect_callback=disconnect_callback,
        )
        self._virtual_base = VirtualServoBase(self.socket, self._lock)

    def _read_raw(self, reg: Register, **kwargs: Any) -> bytes:
        _ = kwargs
        if not isinstance(reg, EthercatRegister):
            raise ILIOError(f"Expected EthercatRegister, got {type(reg)}")
        frame_data = {
            "command": "read",
            "index": reg.idx,
            "subindex": reg.subidx,
            "subnode": reg.subnode,
        }
        return self._virtual_base.exchange_serialized_frame(
            frame_data, self._deserialize_read_response
        )

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
            "subnode": reg.subnode,
            "data": data,
        }
        self._virtual_base.exchange_serialized_frame(frame_data, self._deserialize_write_response)

    @staticmethod
    def _deserialize_read_response(response: object) -> bytes:
        if isinstance(response, bytes):
            return response

        if isinstance(response, dict):
            if "error" in response:
                raise ILIOError(str(response["error"]))
            data = response.get("data")
            if isinstance(data, bytes):
                return data

        raise ILIOError(f"Unexpected response type for read operation: {type(response)}")

    @staticmethod
    def _deserialize_write_response(response: object) -> None:
        if isinstance(response, dict) and "error" in response:
            raise ILIOError(str(response["error"]))
        return None
