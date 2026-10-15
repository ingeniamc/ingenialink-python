from enum import Enum, auto


class NodeMode(Enum):
    """Operating modes of a node."""

    APPLICATION = auto()
    BOOTLOADER = auto()
