from enum import Enum


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
