from enum import Enum


class SERVO_STATE(Enum):
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


class SERVO_FLAGS(Enum):
    """Status Flags."""
    TGT_REACHED = 0x01
    """Target reached."""
    ILIM_ACTIVE = 0x02
    """Internal limit active."""
    HOMING_ATT = 0x04
    """(Homing) attained."""
    HOMING_ERR = 0x08
    """(Homing) error."""
    PV_VZERO = 0x04
    """(PV) Vocity speed is zero."""
    PP_SPACK = 0x04
    """(PP) SP acknowledge."""
    IP_ACTIVE = 0x04
    """(IP) active."""
    CS_FOLLOWS = 0x04
    """(CST/CSV/CSP) follow command value."""
    FERR = 0x08
    """(CST/CSV/CSP/PV) following error."""
    IANGLE_DET = 0x10
    """Initial angle determination finished."""


class SERVO_MODE(Enum):
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


class SERVO_UNITS_TORQUE(Enum):
    """Torque Units."""
    NATIVE = 0
    """Native"""
    MN = 1
    """Millinewtons*meter."""
    N = 2
    """Newtons*meter."""


class SERVO_UNITS_POS(Enum):
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


class SERVO_UNITS_VEL(Enum):
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


class SERVO_UNITS_ACC(Enum):
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