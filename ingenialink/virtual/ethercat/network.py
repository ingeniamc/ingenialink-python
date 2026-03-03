import socket
import time
from collections import OrderedDict
from threading import Thread
from typing import Any, Callable, Optional

import ingenialogger
from typing_extensions import override

from ingenialink.constants import DEFAULT_ETH_CONNECTION_TIMEOUT
from ingenialink.ethercat.network import EthercatNetworkBase
from ingenialink.exceptions import ILError
from ingenialink.network import NetDevEvt, NetState, SlaveInfo
from ingenialink.servo import Servo
from ingenialink.virtual.base_network import VirtualNetworkBase
from ingenialink.virtual.ethercat.servo import VirtualEthercatServo

logger = ingenialogger.get_logger(__name__)


class VirtualNetStatusListener(Thread):
    """Network status listener for virtual EtherCAT servos.

    Periodically checks whether each servo is alive and emits
    connection/disconnection events when the state changes.

    Args:
        network: The virtual EtherCAT network instance.
        refresh_time: How often to poll servo status, in seconds.

    """

    def __init__(self, network: "VirtualEthercatNetwork", refresh_time: float = 0.25) -> None:
        super().__init__()
        self.__network = network
        self.__refresh_time = refresh_time
        self.__stop = False

    def run(self) -> None:
        """Continuously check the status of all servos in the network."""
        while not self.__stop:
            try:
                for servo in self.__network.servos:
                    slave_id = servo.slave_id
                    servo_state = self.__network.get_servo_state(slave_id)
                    is_servo_alive = servo.is_alive()
                    if servo_state == NetState.CONNECTED and not is_servo_alive:
                        self.__network._notify_status(slave_id, NetDevEvt.REMOVED)
                        self.__network._set_servo_state(slave_id, NetState.DISCONNECTED)
                    if (
                        servo_state == NetState.DISCONNECTED
                        and is_servo_alive
                        and self.__network.recover_from_disconnection(servo)
                    ):
                        self.__network._notify_status(slave_id, NetDevEvt.ADDED)
                        self.__network._set_servo_state(slave_id, NetState.CONNECTED)
            except Exception as e:
                logger.exception(f"Exception during virtual EtherCAT status check: {e}")
            time.sleep(self.__refresh_time)

    def stop(self) -> None:
        """Stop the listener."""
        self.__stop = True


class VirtualEthercatNetwork(EthercatNetworkBase):
    """Network for all virtual EtherCAT drive communications."""

    def __init__(self) -> None:
        super().__init__()
        self._virtual_base = VirtualNetworkBase()
        self.__listener_net_status: Optional[VirtualNetStatusListener] = None

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
        servo._disconnect_event_publisher.notify(servo)

    def start_status_listener(self) -> None:
        """Start monitoring network events (CONNECTION/DISCONNECTION)."""
        if self.__listener_net_status is None:
            listener = VirtualNetStatusListener(self)
            listener.start()
            self.__listener_net_status = listener

    def stop_status_listener(self) -> None:
        """Stop the network status listener."""
        if self.__listener_net_status is not None:
            self.__listener_net_status.stop()
            self.__listener_net_status.join()
        self.__listener_net_status = None

    @override
    def recover_from_disconnection(self, servo: Optional[Servo] = None) -> bool:
        """The virtual EtherCAT network does not need to perform any action on disconnection.

        Args:
            servo: The servo that was disconnected, if applicable.

        Returns:
            True, indicating that the network is ready to accept new connections.


        """
        return True

    @override
    def load_firmware(*_args: Any, **_kwargs: Any) -> None:
        """Load firmware to a virtual EtherCAT drive.

        Raises:
            NotImplementedError: Firmware loading is not supported by this network.

        """
        raise NotImplementedError("Firmware loading is not supported for Virtual EtherCAT.")


__all__ = ["VirtualEthercatNetwork"]
