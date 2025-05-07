import warnings
from enum import Enum
from typing import Any


class ServoState(Enum):
    """Servo states."""

    NRDY = 0
    """Not ready to switch on."""
    DISABLED = 1
    """Switch on disabled."""
    RDY = 2
    """Ready to be switched on."""
    ON = 3
    """Power switched on."""
    ENABLED = 4
    """Enabled."""
    QSTOP = 5
    """Quick stop."""
    FAULTR = 6
    """Fault reactive."""
    FAULT = 7
    """Fault."""


class ServoMode(Enum):
    """Operation Mode."""

    OLV = 0
    """Open loop (vector mode)."""
    OLS = 1
    """Open loop (scalar mode)."""
    PP = 2
    """Profile position mode."""
    VEL = 3
    """Velocity mode."""
    PV = 4
    """Profile velocity mode."""
    PT = 5
    """Profile torque mode."""
    HOMING = 6
    """Homing mode."""
    IP = 7
    """Interpolated position mode."""
    CSP = 8
    """Cyclic sync position mode."""
    CSV = 9
    """Cyclic sync velocity mode."""
    CST = 10
    """Cyclic sync torque mode."""


class ServoUnitsTorque(Enum):
    """Torque Units."""

    NATIVE = 0
    """Native"""
    MN = 1
    """Millinewtons*meter."""
    N = 2
    """Newtons*meter."""


class ServoUnitsPos(Enum):
    """Position Units."""

    NATIVE = 0
    """Native."""
    REV = 1
    """Revolutions."""
    RAD = 2
    """Radians."""
    DEG = 3
    """Degrees."""
    UM = 4
    """Micrometers."""
    MM = 5
    """Millimeters."""
    M = 6
    """Meters."""


class ServoUnitsVel(Enum):
    """Velocity Units."""

    NATIVE = 0
    """Native."""
    RPS = 1
    """Revolutions per second."""
    RPM = 2
    """Revolutions per minute."""
    RAD_S = 3
    """Radians/second."""
    DEG_S = 4
    """Degrees/second."""
    UM_S = 5
    """Micrometers/second."""
    MM_S = 6
    """Millimeters/second."""
    M_S = 7
    """Meters/second."""


class ServoUnitsAcc(Enum):
    """Acceleration Units."""

    NATIVE = 0
    """Native."""
    REV_S2 = 1
    """Revolutions/second^2."""
    RAD_S2 = 2
    """Radians/second^2."""
    DEG_S2 = 3
    """Degrees/second^2."""
    UM_S2 = 4
    """Micrometers/second^2."""
    MM_S2 = 5
    """Millimeters/second^2."""
    M_S2 = 6
    """Meters/second^2."""


# WARNING: Deprecated aliases
_DEPRECATED = {
    "SERVO_STATE": "ServoState",
    "SERVO_MODE": "ServoMode",
    "SERVO_UNITS_TORQUE": "ServoUnitsTorque",
    "SERVO_UNITS_POS": "ServoUnitsPos",
    "SERVO_UNITS_VEL": "ServoUnitsVel",
    "SERVO_UNITS_ACC": "ServoUnitsAcc",
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
