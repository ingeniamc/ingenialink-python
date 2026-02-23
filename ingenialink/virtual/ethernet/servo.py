from typing import Callable, Optional

from ingenialink import Servo
from ingenialink.constants import DEFAULT_ETH_CONNECTION_TIMEOUT
from ingenialink.dictionary import Interface
from ingenialink.ethernet.servo import EthernetServo
from ingenialink.virtual.servo import VirtualServoBase


class VirtualEthernetServo(EthernetServo):
    """Virtual Ethernet servo implementation."""

    interface = Interface.VIRTUAL

    def __init__(
        self,
        target: str,
        dictionary_path: str,
        port: int = 1061,
        connection_timeout: float = DEFAULT_ETH_CONNECTION_TIMEOUT,
        servo_status_listener: bool = False,
        is_eoe: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ) -> None:
        super().__init__(
            target,
            dictionary_path,
            port,
            connection_timeout,
            servo_status_listener,
            is_eoe,
            disconnect_callback,
        )
        self._virtual_base = VirtualServoBase()
