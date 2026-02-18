import socket
from collections import OrderedDict, defaultdict
from typing import Any, Callable, Optional, Union

from ingenialink.constants import DEFAULT_ETH_CONNECTION_TIMEOUT
from ingenialink.ethercat.network import EthercatNetworkBase
from ingenialink.exceptions import ILError
from ingenialink.network import NetDevEvt, NetProt, NetState, SlaveInfo
from ingenialink.servo import Servo
from ingenialink.virtual.base_network import VirtualNetworkBase
from ingenialink.virtual.ethercat.servo import VirtualEthercatServo


class VirtualEthercatNetwork(EthercatNetworkBase):
    """Network for all virtual EtherCAT drive communications."""

    def __init__(self) -> None:
        super().__init__()
        self._virtual_base = VirtualNetworkBase()
        self.__observers_net_state: dict[int, list[Callable[[NetDevEvt], Any]]] = defaultdict(list)

    def scan_slaves(self) -> list[int]:
        """Scan for virtual EtherCAT drives.

        Returns:
            List of discovered slave IDs.

        """
        if self.servos:
            return [servo.slave_id for servo in self.servos]
        return []

    def scan_slaves_info(self) -> OrderedDict[int, SlaveInfo]:
        """Scan for virtual EtherCAT drives and retrieve basic info.

        Returns:
            Ordered dictionary of slave IDs and their basic information.

        """
        return OrderedDict((slave_id, SlaveInfo()) for slave_id in self.scan_slaves())

    def connect_to_slave(
        self,
        slave_id: int,
        dictionary: str,
        port: int = 1061,
        connection_timeout: float = DEFAULT_ETH_CONNECTION_TIMEOUT,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ) -> VirtualEthercatServo:
        """Connects to a drive through a given slave number.

        Args:
            slave_id: Targeted slave to be connected.
            dictionary: Path to the dictionary file.
            port: Port to connect to the slave.
            connection_timeout: Time in seconds of the connection timeout.
            servo_status_listener: Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener: Toggle the listener of the network
                status, connection and disconnection.
            disconnect_callback: Callback function to be called when the servo is disconnected.
                If not specified, no callback will be called.

        Raises:
            ILError: If the drive is not reachable through the configured connection.

        Returns:
            VirtualEthercatServo: Instance of the servo connected.
        """
        sock = self._virtual_base.create_connection(connection_timeout, port)
        servo = VirtualEthercatServo(
            sock,
            slave_id,
            dictionary,
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
        self._set_servo_state(slave_id, NetState.CONNECTED)

        if net_status_listener:
            self.start_status_listener()
        else:
            self.stop_status_listener()
        return servo

    def disconnect_from_slave(self, servo: Servo) -> None:
        """Disconnects the slave from the network.

        Args:
            servo: Instance of the connected virtual EtherCAT servo.

        Raises:
            ValueError: If the provided servo is not a virtual EtherCAT servo.

        """
        if not isinstance(servo, VirtualEthercatServo):
            raise ValueError("Virtual EtherCAT Servo instance must be provided.")
        self.servos.remove(servo)
        servo.stop_status_listener()
        servo.socket.shutdown(socket.SHUT_RDWR)
        servo.socket.close()
        self._set_servo_state(servo.slave_id, NetState.DISCONNECTED)
        if len(self.servos) == 0:
            self.stop_status_listener()
        if servo._disconnect_callback:
            servo._disconnect_callback(servo)

    def recover_from_disconnection(self, servo: Optional[Servo] = None) -> bool:
        """Recover communication with a disconnected servo.

        Args:
            servo: Servo instance to recover.

        Raises:
            ValueError: If the provided servo is invalid.

        Returns:
            ``True`` when communication appears to be active, ``False`` otherwise.

        """
        if servo is None or not isinstance(servo, VirtualEthercatServo):
            raise ValueError("Virtual EtherCAT Servo instance must be provided for recovery.")
        return servo.socket.fileno() != -1

    @staticmethod
    def load_firmware(*_args: Any, **_kwargs: Any) -> None:
        """Load firmware to a virtual EtherCAT drive.

        Raises:
            NotImplementedError: Firmware loading is not supported by this network.

        """
        raise NotImplementedError("Firmware loading is not supported for Virtual EtherCAT.")

    def subscribe_to_status(
        self, target: Union[int, str], callback: Callable[[NetDevEvt], Any]
    ) -> None:
        """Subscribe to connection status changes.

        Args:
            target: Target slave ID.
            callback: Callback function to execute on state changes.

        Raises:
            ValueError: If the target ID type is invalid.

        """
        if not isinstance(target, int):
            raise ValueError("The servo ID must be an integer.")
        if callback in self.__observers_net_state[target]:
            return
        self.__observers_net_state[target].append(callback)

    def unsubscribe_from_status(
        self, target: Union[int, str], callback: Callable[[NetDevEvt], Any]
    ) -> None:
        """Unsubscribe from connection status changes.

        Args:
            target: Target slave ID.
            callback: Callback function previously subscribed.

        Raises:
            ValueError: If the target ID type is invalid.

        """
        if not isinstance(target, int):
            raise ValueError("The servo ID must be an integer.")
        if callback not in self.__observers_net_state[target]:
            return
        self.__observers_net_state[target].remove(callback)

    def start_status_listener(self) -> None:
        """Start monitoring network state.

        Status monitoring is not currently implemented for virtual EtherCAT.
        """
        return None

    def stop_status_listener(self) -> None:
        """Stop monitoring network state.

        Status monitoring is not currently implemented for virtual EtherCAT.
        """
        return None

    def get_servo_state(self, servo_id: Union[int, str]) -> NetState:
        """Get the state of a servo in the network.

        Args:
            servo_id: Servo ID.

        Raises:
            ValueError: If the servo ID type is invalid.

        Returns:
            Current state of the servo.

        """
        if not isinstance(servo_id, int):
            raise ValueError("The servo ID must be an integer.")
        return self._servos_state[servo_id]

    def _set_servo_state(self, servo_id: Union[int, str], state: NetState) -> None:
        """Set the state of a servo in the network.

        Args:
            servo_id: Servo ID.
            state: New servo state.

        Raises:
            ValueError: If the servo ID type is invalid.

        """
        if not isinstance(servo_id, int):
            raise ValueError("The servo ID must be an integer.")
        self._servos_state[servo_id] = state

    @property
    def protocol(self) -> NetProt:
        """Obtain network protocol."""
        return NetProt.ECAT


__all__ = ["VirtualEthercatNetwork"]
