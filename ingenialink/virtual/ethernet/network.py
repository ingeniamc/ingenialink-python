from typing import Callable, Optional

from ingenialink.constants import DEFAULT_ETH_CONNECTION_TIMEOUT
from ingenialink.ethernet.network import EthernetNetworkBase
from ingenialink.exceptions import ILError
from ingenialink.network import NetState
from ingenialink.servo import Servo
from ingenialink.virtual.base_network import VirtualNetworkBase
from ingenialink.virtual.ethernet.servo import VirtualEthernetServo


class VirtualEthernetNetwork(EthernetNetworkBase):
    """Network for all virtual Ethernet drive communications."""

    def __init__(self) -> None:
        super().__init__()
        self._virtual_base = VirtualNetworkBase()

    def connect_to_slave(  # type: ignore [override]
        self,
        dictionary: str,
        port: int = 1061,
        connection_timeout: float = DEFAULT_ETH_CONNECTION_TIMEOUT,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ) -> VirtualEthernetServo:
        """Connects to a slave through the given network settings.

        Args:
            dictionary: Path to the target dictionary file.
            port: Port to connect to the slave.
            connection_timeout: Time in seconds of the connection timeout.
            servo_status_listener: Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener: Toggle the listener of the network
                status, connection and disconnection.
            disconnect_callback: Callback function to be called when the servo is disconnected.
                If not specified, no callback will be called.

        Raises:
            ILError: if the drive is not found in IP.

        Returns:
            VirtualEthernetServo: Instance of the servo connected.
        """
        servo = VirtualEthernetServo(
            self._virtual_base.virtual_drive_ip_address,
            dictionary,
            port,
            connection_timeout,
            servo_status_listener,
            disconnect_callback=disconnect_callback,
        )
        try:
            servo.get_state()
        except ILError as e:
            servo.stop_status_listener()
            raise ILError(
                f"Drive not found in IP {self._virtual_base.virtual_drive_ip_address}."
            ) from e
        self.servos.append(servo)
        self._set_servo_state(self._virtual_base.virtual_drive_ip_address, NetState.CONNECTED)

        if net_status_listener:
            self.start_status_listener()
        else:
            self.stop_status_listener()
        return servo


__all__ = ["VirtualEthernetNetwork"]
