import warnings
from abc import ABC, abstractmethod
from collections import OrderedDict
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
    def load_firmware(self, *args: Any, **kwargs: Any) -> None:
        """Loads a given firmware file to a target drive.

        Args:
            *args: Protocol dependent positional arguments.
            **kwargs: Protocol dependent keyword arguments.

        """
        raise NotImplementedError

    @abstractmethod
    def subscribe_to_status(
        self, target: Union[int, str], callback: Callable[[NetDevEvt], Any]
    ) -> None:
        """Subscribe to network state changes.

        Args:
            target: ID of the drive to subscribe.
            callback: Callback function.

        """
        raise NotImplementedError

    @abstractmethod
    def unsubscribe_from_status(
        self, target: Union[int, str], callback: Callable[[NetDevEvt], Any]
    ) -> None:
        """Unsubscribe from network state changes.

        Args:
            target: ID of the drive to subscribe.
            callback: Callback function.

        """
        raise NotImplementedError

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

    @abstractmethod
    def _set_servo_state(self, servo_id: Union[int, str], state: NetState) -> None:
        self._servos_state[servo_id] = state

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
