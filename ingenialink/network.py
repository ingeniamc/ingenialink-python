from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

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


class EepromFileFormat(Enum):
    """EEPROM file format"""

    BINARY = 0
    INTEL = 1


# WARNING: Deprecated aliases
NET_PROT = NetProt
NET_STATE = NetState
NET_DEV_EVT = NetDevEvt
EEPROM_FILE_FORMAT = EepromFileFormat


# FIXME: INGK-1022
class NET_TRANS_PROT(Enum):
    """Transmission protocol."""

    TCP = 1
    UDP = 2


@dataclass
class SlaveInfo:
    product_code: Optional[int] = None
    revision_number: Optional[int] = None


class Network(ABC):
    """Declaration of a general Network object."""

    def __init__(self) -> None:
        self.servos: List[Any] = []
        """List of the connected servos in the network."""

        self._servos_state: Dict[Union[int, str], NetState] = {}
        """Dictionary containing the state of the servos that are a part of the network."""

    @abstractmethod
    def scan_slaves(self) -> List[int]:
        raise NotImplementedError

    @abstractmethod
    def scan_slaves_info(self) -> OrderedDict[int, SlaveInfo]:
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
    def subscribe_to_status(
        self, target: Union[int, str], callback: Callable[[NetDevEvt], Any]
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def unsubscribe_from_status(
        self, target: Union[int, str], callback: Callable[[NetDevEvt], Any]
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def start_status_listener(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop_status_listener(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_servo_state(self, servo_id: Union[int, str]) -> NetState:
        return self._servos_state[servo_id]

    @abstractmethod
    def _set_servo_state(self, servo_id: Union[int, str], state: NetState) -> None:
        self._servos_state[servo_id] = state

    @property
    def protocol(self) -> NetProt:
        raise NotImplementedError
