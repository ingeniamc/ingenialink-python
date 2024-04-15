from enum import Enum


class REG_DTYPE(Enum):
    """Data Type."""

    U8 = 0
    """Unsigned 8-bit integer."""
    S8 = 1
    """Signed 8-bit integer."""
    U16 = 2
    """Unsigned 16-bit integer."""
    S16 = 3
    """Signed 16-bit integer."""
    U32 = 4
    """Unsigned 32-bit integer."""
    S32 = 5
    """Signed 32-bit integer."""
    U64 = 6
    """Unsigned 64-bit integer."""
    S64 = 7
    """Signed 64-bit integer."""
    FLOAT = 8
    """Float."""
    STR = 10
    """String."""
    BYTE_ARRAY_512 = 15
    """Buffer with size of 512 bytes."""
    BOOL = 99
    """Boolean."""


class REG_ACCESS(Enum):
    """Access Type."""

    RW = 0
    """Read/Write."""
    RO = 1
    """Read-only."""
    WO = 2
    """Write-only."""


class REG_PHY(Enum):
    """Physical Units."""

    NONE = 0
    """None."""
    TORQUE = 1
    """Torque."""
    POS = 2
    """Position."""
    VEL = 3
    """Velocity."""
    ACC = 4
    """Acceleration."""
    VOLT_REL = 5
    """Relative voltage (DC)."""
    RAD = 6
    """Radians."""


class REG_ADDRESS_TYPE(Enum):
    """Address Type."""

    NVM = 0
    NVM_NONE = 1
    NVM_CFG = 2
    NVM_LOCK = 3
    NVM_HW = 4


class RegCyclicType(Enum):
    """Cyclic Type."""

    RX = "CYCLIC_RX"
    TX = "CYCLIC_TX"
    TXRX = "CYCLIC_TXRX"
    CONFIG = "CONFIG"
