from typing import Callable, Optional

from ingenialink.ethercat.network import EthercatNetworkBase
from ingenialink.servo import Servo
from ingenialink.virtual.base_network import VirtualNetworkBase


class VirtualEthercatNetwork(EthercatNetworkBase):
    """Network for all virtual EtherCAT drive communications."""

    def __init__(self) -> None:
        super().__init__()
        self._virtual_base = VirtualNetworkBase()

    def connect_to_slave(
        self,
        slave_id: int,
        dictionary: str,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ) -> Servo:
        """Connects to a drive through a given slave number.

        Args:
            slave_id: Targeted slave to be connected.
            dictionary: Path to the dictionary file.
            servo_status_listener: Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener: Toggle the listener of the network
                status, connection and disconnection.
            disconnect_callback: Callback function to be called when the servo is disconnected.
                If not specified, no callback will be called.

        Returns:
            Virtual EtherCAT servo.
        """
        raise NotImplementedError("Virtual EtherCAT network not yet implemented")


__all__ = ["VirtualEthercatNetwork"]
