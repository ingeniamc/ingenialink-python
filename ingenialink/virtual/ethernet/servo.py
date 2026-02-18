import socket
from typing import Callable, Optional

import ingenialogger

from ingenialink import Servo
from ingenialink.constants import MCB_CMD_READ, MCB_CMD_WRITE
from ingenialink.dictionary import Interface
from ingenialink.ethernet.register import EthernetRegister
from ingenialink.ethernet.servo import EthernetServoBase
from ingenialink.exceptions import ILTimeoutError, ILWrongRegisterError
from ingenialink.utils.mcb import MCB
from ingenialink.virtual.servo import VirtualServoBase

logger = ingenialogger.get_logger(__name__)


class VirtualEthernetServo(EthernetServoBase):
    """Virtual Ethernet servo implementation."""

    interface = Interface.VIRTUAL

    def __init__(
        self,
        socket: socket.socket,
        dictionary_path: str,
        servo_status_listener: bool = False,
        is_eoe: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ) -> None:
        super().__init__(
            socket,
            dictionary_path,
            servo_status_listener,
            is_eoe,
            disconnect_callback,
        )
        self._virtual_base = VirtualServoBase(self.socket, self._lock)

    def _write_raw(self, reg: EthernetRegister, data: bytes) -> None:  # type: ignore [override]
        self._send_mcb_frame(MCB_CMD_WRITE, reg.address, reg.subnode, data)

    def _read_raw(self, reg: EthernetRegister) -> bytes:  # type: ignore [override]
        return self._send_mcb_frame(MCB_CMD_READ, reg.address, reg.subnode)

    def _send_mcb_frame(
        self, cmd: int, reg: int, subnode: int, data: Optional[bytes] = None
    ) -> bytes:
        frame = MCB.build_mcb_frame(cmd, subnode, reg, data)
        with self._virtual_base.transaction():
            self._virtual_base.send_frame(frame)
            try:
                return MCB.read_mcb_data(reg, self._virtual_base.receive_frame())
            except ILWrongRegisterError as e:
                logger.error(e)
                return MCB.read_mcb_data(reg, self._virtual_base.receive_frame())
            except ILTimeoutError as e:
                logger.error(f"{e}. Retrying..")
                self._virtual_base.send_frame(frame)
                return MCB.read_mcb_data(reg, self._virtual_base.receive_frame())
