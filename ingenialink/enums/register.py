import warnings
from enum import Enum
from typing import Any


class RegDtype(Enum):
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


class RegAccess(Enum):
    """Access Type."""

    RW = 0
    """Read/Write."""
    RO = 1
    """Read-only."""
    WO = 2
    """Write-only."""


class RegPhy(Enum):
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


class RegAddressType(Enum):
    """Address Type."""

    NVM = 0
    NVM_NONE = 1
    NVM_CFG = 2
    NVM_LOCK = 3
    NVM_HW = 4
    NVM_INDIRECT = 5


class RegCyclicType(Enum):
    """Cyclic Type."""

    RX = "CYCLIC_RX"
    TX = "CYCLIC_TX"
    RXTX = "CYCLIC_RXTX"
    CONFIG = "CONFIG"
    SAFETY_INPUT = "CYCLIC_SI"
    SAFETY_OUTPUT = "CYCLIC_SO"
    SAFETY_INPUT_OUTPUT = "CYCLIC_SISO"


_DEPRECATED = {
    "REG_DTYPE": "RegDtype",
    "REG_ACCESS": "RegAccess",
    "REG_PHY": "RegPhy",
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
