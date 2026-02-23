from typing import Callable, Optional

from ingenialink.canopen.network import CanopenNetworkBase
from ingenialink.servo import Servo
from ingenialink.virtual.base_network import VirtualNetworkBase


class VirtualCanopenNetwork(CanopenNetworkBase):
    """Network for all virtual CANopen drive communications."""

    def __init__(self) -> None:
        super().__init__()
        self._virtual_base = VirtualNetworkBase()

    def connect_to_slave(
        self,
        target: int,
        dictionary: str,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ) -> Servo:
        """Connects to a drive through a given target node ID.

        Args:
            target: Targeted node ID to be connected.
            dictionary: Path to the dictionary file.
            servo_status_listener: Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener: Toggle the listener of the network
                status, connection and disconnection.
            disconnect_callback: Callback function to be called when the servo is disconnected.
                If not specified, no callback will be called.

        Returns:
            Virtual CANopen servo.
        """
        raise NotImplementedError("It will be implemented in SVD-35")


__all__ = ["VirtualCanopenNetwork"]
