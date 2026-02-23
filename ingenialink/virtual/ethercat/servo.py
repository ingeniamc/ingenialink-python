import socket
from typing import Any, Callable, Optional

from typing_extensions import override

from ingenialink import Servo
from ingenialink.constants import ETH_BUF_SIZE
from ingenialink.dictionary import Interface
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.ethercat.servo import EthercatServoBase
from ingenialink.exceptions import ILIOError
from ingenialink.register import Register
from ingenialink.virtual.ethercat.codec import deserialize_sdo_frame, serialize_sdo_frame
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
            servo_status_listener,
            disconnect_callback=disconnect_callback,
        )
        self._virtual_base = VirtualServoBase(self.socket, self._lock)

    def _exchange_sdo_frame(self, frame_data: dict[str, Any]) -> dict[str, Any]:
        with self._virtual_base.transaction():
            self._virtual_base.send_frame(serialize_sdo_frame(frame_data))
            response_frame = self._virtual_base.receive_frame(ETH_BUF_SIZE)

        try:
            return deserialize_sdo_frame(response_frame)
        except (UnicodeDecodeError, ValueError, TypeError) as e:
            raise ILIOError("Error deserializing EtherCAT SDO response data.") from e

    def _read_raw(self, reg: Register, **kwargs: Any) -> bytes:
        _ = kwargs
        if not isinstance(reg, EthercatRegister):
            raise ILIOError(f"Expected EthercatRegister, got {type(reg)}")
        frame_data = {
            "command": "read",
            "index": reg.idx,
            "subindex": reg.subidx,
        }
        response = self._exchange_sdo_frame(frame_data)
        return self._deserialize_read_response(response)

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
        response = self._exchange_sdo_frame(frame_data)
        self._deserialize_write_response(response)

    @override
    def check_servo_is_in_preoperational_state(self) -> None:
        pass

    @staticmethod
    def _deserialize_read_response(response: object) -> bytes:
        if isinstance(response, bytes):
            return response

        if isinstance(response, dict):
            if "error_code" in response:
                raise ILIOError(f"Error code {response['error_code']} received in read response")
            data = response.get("data")
            if isinstance(data, bytes):
                return data

        raise ILIOError(f"Unexpected response type for read operation: {type(response)}")

    @staticmethod
    def _deserialize_write_response(response: object) -> None:
        if not isinstance(response, (dict)):
            raise ILIOError(f"Unexpected response type for write operation: {type(response)}")
        if "error_code" in response:
            raise ILIOError(f"Error code {response['error_code']} received in write response")
        return None
