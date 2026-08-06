from collections import OrderedDict
from typing import Any, Callable, Optional

from ingenialink.ethernet.network import NetStatusListener
from ingenialink.ethernet.tsn.sdcp.connection import DEFAULT_SDCP_TIMEOUT_S
from ingenialink.exceptions import ILStateError
from ingenialink.network import NetProt, NetState, Network, ServoTarget, SlaveInfo
from ingenialink.servo import Servo
from ingenialink.virtual.sdcp.servo import VirtualSDCPServo

VIRTUAL_SDCP_TARGET = "::1"


class VirtualSDCPNetwork(Network[VirtualSDCPServo]):
    """Network for the virtual SDCP drive on the IPv6 loopback address."""

    def __init__(self) -> None:
        super().__init__()
        self.__listener_net_status: Optional[NetStatusListener[VirtualSDCPServo]] = None

    @property
    def protocol(self) -> NetProt:
        """Obtain the network protocol."""
        return NetProt.ETH

    def scan_slaves(self) -> list[str]:  # type: ignore[override]
        """Return the known virtual SDCP drive address."""
        return [servo.target for servo in self.servos if isinstance(servo.target, str)]

    def scan_slaves_info(self) -> OrderedDict[str, SlaveInfo]:  # type: ignore[override]
        """Return basic information for the known virtual SDCP drive."""
        return OrderedDict((target, SlaveInfo()) for target in self.scan_slaves())

    def connect_to_slave(
        self,
        dictionary: str,
        connection_timeout: float = DEFAULT_SDCP_TIMEOUT_S,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ) -> VirtualSDCPServo:
        """Connect to the virtual SDCP drive without performing discovery.

        Returns:
            The connected virtual SDCP servo.

        Raises:
            ILStateError: If the virtual drive is already connected.
        """
        _ = net_status_listener
        if self.servos:
            raise ILStateError("The virtual SDCP drive is already connected")

        servo = VirtualSDCPServo(
            target=VIRTUAL_SDCP_TARGET,
            dictionary_path=dictionary,
            connection_timeout=connection_timeout,
            servo_status_listener=servo_status_listener,
            disconnect_callback=disconnect_callback,
        )
        self.servos.append(servo)
        self._set_servo_state(servo, NetState.CONNECTED)
        if net_status_listener:
            self.start_status_listener()
        return servo

    def disconnect_from_slave(self, servo: Servo) -> None:
        """Disconnect the virtual SDCP servo and close its connection.

        Raises:
            ValueError: If the servo is not a connected virtual SDCP servo.
        """
        if not isinstance(servo, VirtualSDCPServo):
            raise ValueError("Virtual SDCP Servo instance must be provided.")
        if servo not in self.servos:
            raise ValueError("The virtual SDCP Servo is not connected through this network")

        servo.stop_status_listener()
        servo.disconnect()
        self._set_servo_state(servo, NetState.DISCONNECTED)
        self.servos.remove(servo)
        if len(self.servos) == 0:
            self.stop_status_listener()

    def close(self) -> None:
        """Disconnect all virtual SDCP servos."""
        for servo in list(self.servos):
            self.disconnect_from_slave(servo)

    def start_status_listener(self) -> None:
        """Start monitoring the virtual SDCP connection status."""
        if self.__listener_net_status is None:
            listener = NetStatusListener(self)
            listener.start()
            self.__listener_net_status = listener

    def stop_status_listener(self) -> None:
        """Stop monitoring the virtual SDCP connection status."""
        if self.__listener_net_status is not None:
            self.__listener_net_status.stop()
            self.__listener_net_status.join()
        self.__listener_net_status = None

    def recover_from_disconnection(self, servo: Optional[Servo] = None) -> bool:
        """The virtual SDCP network requires no recovery action.

        Args:
            servo: Servo whose connection would be recovered.

        Returns:
            Whether the network is ready to accept new connections.
        """
        _ = servo
        return True

    def load_firmware(self, *_args: Any, **_kwargs: Any) -> None:
        """Firmware loading is not supported by the virtual SDCP network."""
        raise NotImplementedError("Firmware loading is not supported for Virtual SDCP.")

    def get_servo_state(self, servo_id: ServoTarget) -> NetState:
        """Return the network state for a virtual SDCP servo."""
        return super().get_servo_state(servo_id)


__all__ = ["VirtualSDCPNetwork"]
