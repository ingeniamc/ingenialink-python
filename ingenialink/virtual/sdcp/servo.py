from typing import Callable, Optional

from ingenialink import Servo
from ingenialink.ethernet.tsn.sdcp.servo import SDCPServo

VIRTUAL_SDCP_INTERFACE = "loopback"


class VirtualSDCPServo(SDCPServo):
    """Virtual SDCP servo using the IPv6 loopback address."""

    def __init__(
        self,
        target: str,
        dictionary_path: str,
        connection_timeout: float = SDCPServo._CONNECTION_TIMEOUT_S,
        servo_status_listener: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ) -> None:
        super().__init__(
            target=target,
            interface=VIRTUAL_SDCP_INTERFACE,
            dictionary_path=dictionary_path,
            connection_timeout=connection_timeout,
            servo_status_listener=servo_status_listener,
            disconnect_callback=disconnect_callback,
        )


__all__ = ["VIRTUAL_SDCP_INTERFACE", "VirtualSDCPServo"]
