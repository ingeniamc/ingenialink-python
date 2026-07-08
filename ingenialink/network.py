import warnings
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Optional, Union

import ingenialogger

from ingenialink.enums.network import NetDevEvt as NetDevEvt
from ingenialink.enums.network import NetProt as NetProt
from ingenialink.enums.network import NetState as NetState
from ingenialink.servo import Servo

logger = ingenialogger.get_logger(__name__)


@dataclass
class SlaveInfo:
    """Class to store slave information."""

    product_code: Optional[int] = None
    revision_number: Optional[int] = None


ServoTarget = Union[int, str, Servo]
"""A servo can be identified either by its raw id (slave id / node id / ip) or by
the :class:`Servo` instance itself."""


class Network(ABC):
    """Declaration of a general Network object."""

    def __init__(self) -> None:
        self.servos: list[Any] = []
        """List of the connected servos in the network."""

        self._servo_registry: dict[Union[int, str], Servo] = {}
        """Best-effort id -> last-known Servo mapping, used to resolve raw ids to
        instances even after a servo has been removed from ``self.servos``."""

    def _resolve_servo(self, target: ServoTarget) -> Optional[Servo]:
        """Resolve a raw id or Servo instance to the corresponding Servo.

        Args:
            target: The servo's id, or the servo instance itself.

        Returns:
            The resolved Servo, or None if it can't be resolved.

        """
        if isinstance(target, Servo):
            self._servo_registry[target.target] = target
            return target
        servo: Servo
        for servo in self.servos:
            if servo.target == target:
                self._servo_registry[target] = servo
                return servo
        return self._servo_registry.get(target)

    @abstractmethod
    def scan_slaves(self) -> list[int]:
        """Scans for drives in the network."""
        raise NotImplementedError

    @abstractmethod
    def scan_slaves_info(self) -> OrderedDict[int, SlaveInfo]:
        """Scans for drives in the network.

        Returns:
            Detected drives with their information.

        """
        raise NotImplementedError

    @abstractmethod
    def connect_to_slave(self, *args: Any, **kwargs: Any) -> Servo:
        """Connects to a drive through a given the drive ID.

        Args:
            *args: Protocol dependent positional arguments.
            **kwargs: Protocol dependent keyword arguments.

        """
        raise NotImplementedError

    @abstractmethod
    def disconnect_from_slave(self, servo: Servo) -> None:
        """Disconnects the drive from the network.

        Args:
            servo: Instance of the servo connected.

        """
        raise NotImplementedError

    @abstractmethod
    def recover_from_disconnection(self, servo: Optional[Servo] = None) -> bool:
        """Recovers the connection to a previously disconnected drive.

        Args:
            servo: Instance of the servo to recover.
                For some protocols, this argument might be optional.

        Returns:
            True if communication is recovered, False otherwise.

        """
        raise NotImplementedError

    @abstractmethod
    def load_firmware(self, *args: Any, **kwargs: Any) -> None:
        """Loads a given firmware file to a target drive.

        Args:
            *args: Protocol dependent positional arguments.
            **kwargs: Protocol dependent keyword arguments.

        """
        raise NotImplementedError

    def subscribe_to_status(
        self, target: ServoTarget, callback: Callable[[NetDevEvt], Any]
    ) -> None:
        """Subscribe to network state changes.

        Args:
            target: ID of the drive to subscribe, or the servo instance itself.
            callback: Callback function.

        """
        servo = self._resolve_servo(target)
        if servo is None:
            logger.info("Servo not found, cannot subscribe.")
            return
        servo._net_state_observers.subscribe(callback)

    def unsubscribe_from_status(
        self, target: ServoTarget, callback: Callable[[NetDevEvt], Any]
    ) -> None:
        """Unsubscribe from network state changes.

        Args:
            target: ID of the drive to subscribe, or the servo instance itself.
            callback: Callback function.

        """
        servo = self._resolve_servo(target)
        if servo is None:
            return
        servo._net_state_observers.unsubscribe(callback)

    def _notify_status(self, target: ServoTarget, status: NetDevEvt) -> None:
        """Notify subscribers of a network state change.

        Args:
            target: ID of the drive whose state changed, or the servo instance itself.
            status: New status to notify subscribers with.

        """
        servo = self._resolve_servo(target)
        if servo is None:
            return
        servo._net_state_publisher.notify(status)

    def _clear_observers(self, servo_id: ServoTarget) -> None:
        """Discard all subscribers registered for a servo.

        Must be called when a servo disconnects, so its stale subscriber list
        isn't kept around indefinitely.

        Args:
            servo_id: The servo's ID, or the servo instance itself.

        """
        servo = self._resolve_servo(servo_id)
        if servo is None:
            return
        servo._net_state_observers.clear()

    @abstractmethod
    def start_status_listener(self, *args: Any, **kwargs: Any) -> None:
        """Start monitoring network events (CONNECTION/DISCONNECTION)."""
        raise NotImplementedError

    @abstractmethod
    def stop_status_listener(self, *args: Any, **kwargs: Any) -> None:
        """Stops the NetStatusListener from listening to the drive."""
        raise NotImplementedError

    @abstractmethod
    def get_servo_state(self, servo_id: ServoTarget) -> NetState:
        """Get the state of a servo that's a part of network.

        The state indicates if the servo is connected or disconnected.

        Args:
            servo_id: The servo's ID, or the servo instance itself.

        Raises:
            KeyError: If the servo can't be resolved, or its state was never set.

        Returns:
            The servo's state.

        """
        servo = self._resolve_servo(servo_id)
        if servo is None or servo._net_state is None:
            raise KeyError(servo_id)
        return servo._net_state

    def _set_servo_state(self, servo_id: ServoTarget, state: NetState) -> None:
        """Set the state of a servo that's a part of network.

        Args:
            servo_id: The servo's ID, or the servo instance itself.
            state: The servo's state.

        Raises:
            KeyError: If the servo can't be resolved.

        """
        servo = self._resolve_servo(servo_id)
        if servo is None:
            raise KeyError(servo_id)
        servo._net_state = state

    def _transition_servo_state(self, servo_id: ServoTarget, event: NetDevEvt) -> None:
        """Update a servo's state and notify subscribers of the change, in that order.

        The event fully determines the resulting state (``ADDED`` implies
        ``CONNECTED``, ``REMOVED`` implies ``DISCONNECTED``), so callers only need
        to pass the event.

        The state must be updated before subscribers are notified so that any thread
        woken up by the notification already sees the new state when it calls
        :meth:`get_servo_state`.

        Args:
            servo_id: The servo's ID, or the servo instance itself.
            event: The event to notify subscribers with; determines the new state.

        """
        state = NetState.CONNECTED if event == NetDevEvt.ADDED else NetState.DISCONNECTED
        self._set_servo_state(servo_id, state)
        self._notify_status(servo_id, event)

    @property
    def protocol(self) -> NetProt:
        """NET_PROT: Obtain network protocol."""
        raise NotImplementedError


# WARNING: Deprecated aliases
_DEPRECATED = {
    "NET_PROT": "NetProt",
    "NET_STATE": "NetState",
    "NET_DEV_EVT": "NetDevEvt",
}


def __getattr__(name: str) -> Any:
    if name in _DEPRECATED:
        warnings.warn(
            f"{name} is deprecated, use {_DEPRECATED[name]} instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return globals()[_DEPRECATED[name]]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
