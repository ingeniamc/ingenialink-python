import warnings
from abc import ABC, abstractmethod
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional, Union

import ingenialogger

from ingenialink.servo import Servo

logger = ingenialogger.get_logger(__name__)


class NetProt(Enum):
    """Network Protocol."""

    EUSB = 0
    MCB = 1
    ETH = 2
    ECAT = 3
    CAN = 5


class NetState(Enum):
    """Network State."""

    CONNECTED = 0
    DISCONNECTED = 1
    FAULTY = 2


class NetDevEvt(Enum):
    """Device Event."""

    ADDED = 0
    REMOVED = 1


@dataclass
class SlaveInfo:
    """Class to store slave information."""

    product_code: Optional[int] = None
    revision_number: Optional[int] = None


class Network(ABC):
    """Declaration of a general Network object."""

    def __init__(self) -> None:
        self.servos: list[Any] = []
        """List of the connected servos in the network."""

        self._servos_state: dict[Union[int, str], NetState] = {}
        """Dictionary containing the state of the servos that are a part of the network."""

        self._observers_net_state: dict[Union[int, str], list[Callable[[NetDevEvt], Any]]] = (
            defaultdict(list)
        )
        """Dictionary containing the subscribers to each servo's status changes."""

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
        self, target: Union[int, str], callback: Callable[[NetDevEvt], Any]
    ) -> None:
        """Subscribe to network state changes.

        Args:
            target: ID of the drive to subscribe.
            callback: Callback function.

        """
        if callback in self._observers_net_state[target]:
            logger.info("Callback already subscribed.")
            return
        self._observers_net_state[target].append(callback)

    def unsubscribe_from_status(
        self, target: Union[int, str], callback: Callable[[NetDevEvt], Any]
    ) -> None:
        """Unsubscribe from network state changes.

        Args:
            target: ID of the drive to subscribe.
            callback: Callback function.

        """
        if callback not in self._observers_net_state[target]:
            logger.info("Callback not subscribed.")
            return
        self._observers_net_state[target].remove(callback)

    def _notify_status(self, target: Union[int, str], status: NetDevEvt) -> None:
        """Notify subscribers of a network state change.

        Args:
            target: ID of the drive whose state changed.
            status: New status to notify subscribers with.

        """
        for callback in self._observers_net_state[target]:
            callback(status)

    def _clear_observers(self, servo_id: Union[int, str]) -> None:
        """Discard all subscribers registered for a servo.

        Must be called when a servo disconnects, so its stale subscriber list
        isn't kept around indefinitely.

        Args:
            servo_id: The servo's ID.

        """
        self._observers_net_state.pop(servo_id, None)

    @abstractmethod
    def start_status_listener(self, *args: Any, **kwargs: Any) -> None:
        """Start monitoring network events (CONNECTION/DISCONNECTION)."""
        raise NotImplementedError

    @abstractmethod
    def stop_status_listener(self, *args: Any, **kwargs: Any) -> None:
        """Stops the NetStatusListener from listening to the drive."""
        raise NotImplementedError

    @abstractmethod
    def get_servo_state(self, servo_id: Union[int, str]) -> NetState:
        """Get the state of a servo that's a part of network.

        The state indicates if the servo is connected or disconnected.

        Args:
            servo_id: The servo's ID.

        Returns:
            The servo's state.

        """
        return self._servos_state[servo_id]

    def _set_servo_state(self, servo_id: Union[int, str], state: NetState) -> None:
        """Set the state of a servo that's a part of network.

        Args:
            servo_id: The servo's ID.
            state: The servo's state.

        """
        self._servos_state[servo_id] = state

    def _transition_servo_state(self, servo_id: Union[int, str], event: NetDevEvt) -> None:
        """Update a servo's state and notify subscribers of the change, in that order.

        The event fully determines the resulting state (``ADDED`` implies
        ``CONNECTED``, ``REMOVED`` implies ``DISCONNECTED``), so callers only need
        to pass the event.

        The state must be updated before subscribers are notified so that any thread
        woken up by the notification already sees the new state when it calls
        :meth:`get_servo_state`.

        Args:
            servo_id: The servo's ID.
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
