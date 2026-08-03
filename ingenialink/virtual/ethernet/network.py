from collections import OrderedDict
from typing import Any, Callable, Optional

from typing_extensions import override

from ingenialink.constants import DEFAULT_ETH_CONNECTION_TIMEOUT
from ingenialink.ethernet.network import EthernetNetworkBase
from ingenialink.network import SlaveInfo
from ingenialink.servo import Servo
from ingenialink.virtual.base_network import VirtualNetworkBase
from ingenialink.virtual.ethernet.servo import VirtualEthernetServo


class VirtualEthernetNetwork(EthernetNetworkBase[VirtualEthernetServo]):
    """Network for all virtual Ethernet drive communications."""

    def __init__(self) -> None:
        super().__init__()
        self._virtual_base = VirtualNetworkBase()

    def _create_servo(
        self,
        *,
        target: str,
        dictionary: str,
        port: int,
        connection_timeout: float,
        servo_status_listener: bool,
        is_eoe: bool,
        disconnect_callback: Optional[Callable[[Servo], None]],
    ) -> VirtualEthernetServo:
        return VirtualEthernetServo(
            target,
            dictionary,
            port,
            connection_timeout,
            servo_status_listener,
            is_eoe,
            disconnect_callback=disconnect_callback,
        )

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

        Returns:
            VirtualEthernetServo: Instance of the servo connected.

        Raises:
            ILError: if the drive is not found in IP.
        """
        return super().connect_to_slave(
            target=self._virtual_base.virtual_drive_ip_address,
            dictionary=dictionary,
            port=port,
            connection_timeout=connection_timeout,
            servo_status_listener=servo_status_listener,
            net_status_listener=net_status_listener,
            disconnect_callback=disconnect_callback,
        )

    @override
    def recover_from_disconnection(self, servo: Optional[Servo] = None) -> bool:
        """The virtual Ethernet network does not need to perform any action on disconnection.

        Args:
            servo: The servo that was disconnected, if applicable.

        Returns:
            True, indicating that the network is ready to accept new connections.


        """
        return True

    @override
    def load_firmware(*_args: Any, **_kwargs: Any) -> None:
        """Load firmware to a virtual Ethernet drive.

        Raises:
            NotImplementedError: Firmware loading is not supported by this network.

        """
        raise NotImplementedError("Firmware loading is not supported for Virtual Ethernet.")

    def scan_slaves(self) -> list[str]:  # type: ignore [override]
        """Scan for virtual Ethernet drives.

        Returns:
            List of discovered slave IDs.

        """
        if self.servos:
            return [servo.target for servo in self.servos if isinstance(servo.target, str)]
        return []

    def scan_slaves_info(self) -> OrderedDict[str, SlaveInfo]:  # type: ignore [override]
        """Scan for virtual Ethernet drives and retrieve basic info.

        Returns:
            Ordered dictionary of slave IDs and their basic information.

        """
        return OrderedDict((slave_id, SlaveInfo()) for slave_id in self.scan_slaves())


__all__ = ["VirtualEthernetNetwork"]
