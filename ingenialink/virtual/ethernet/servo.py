import socket
from typing import Callable, Optional

from ingenialink import Servo
from ingenialink.dictionary import Interface
from ingenialink.ethernet.servo import EthernetServoBase
from ingenialink.virtual.servo import VirtualServoBase


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
        self._virtual_base = VirtualServoBase()
