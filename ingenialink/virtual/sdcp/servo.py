from typing import Callable, Optional

from ingenialink import Servo
from ingenialink.ethernet.tsn.sdcp.connection import DEFAULT_SDCP_PORT, SDCPConnection
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
        port: int = DEFAULT_SDCP_PORT,
    ) -> None:
        self._port = port
        super().__init__(
            target=target,
            interface=VIRTUAL_SDCP_INTERFACE,
            dictionary_path=dictionary_path,
            connection_timeout=connection_timeout,
            servo_status_listener=servo_status_listener,
            disconnect_callback=disconnect_callback,
        )

    def _create_connection(
        self,
        target: str,
        interface: str,
        connection_timeout: float,
    ) -> SDCPConnection:
        """Create a connection using the virtual drive's configured port.

        Returns:
            Connection to the virtual SDCP servo.
        """
        return SDCPConnection(target, interface, connection_timeout, self._port)


__all__ = ["VIRTUAL_SDCP_INTERFACE", "VirtualSDCPServo"]
