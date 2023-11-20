from enum import Enum
from abc import ABC, abstractmethod
from typing import List, Any, Callable

import ingenialogger

from ingenialink.servo import Servo

logger = ingenialogger.get_logger(__name__)


class NET_PROT(Enum):
    """Network Protocol."""

    EUSB = 0
    MCB = 1
    ETH = 2
    ECAT = 3
    CAN = 5


class NET_STATE(Enum):
    """Network State."""

    CONNECTED = 0
    DISCONNECTED = 1
    FAULTY = 2


class NET_DEV_EVT(Enum):
    """Device Event."""

    ADDED = 0
    REMOVED = 1


class EEPROM_FILE_FORMAT(Enum):
    """EEPROM file format"""

    BINARY = 0
    INTEL = 1


class NET_TRANS_PROT(Enum):
    """Transmission protocol."""

    TCP = 1
    UDP = 2


class Network(ABC):
    """Declaration of a general Network object."""

    def __init__(self) -> None:
        self.servos: List[Any] = []
        """List of the connected servos in the network."""

    @abstractmethod
    def scan_slaves(self) -> List[int]:
        raise NotImplementedError

    @abstractmethod
    def connect_to_slave(self, *args: Any, **kwargs: Any) -> Servo:
        raise NotImplementedError

    @abstractmethod
    def disconnect_from_slave(self, servo: Servo) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_firmware(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def subscribe_to_status(self, callback: Callable[[NET_DEV_EVT], Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def unsubscribe_from_status(self, callback: Callable[[NET_DEV_EVT], Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def start_status_listener(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop_status_listener(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError

    @property
    def protocol(self) -> NET_PROT:
        raise NotImplementedError
