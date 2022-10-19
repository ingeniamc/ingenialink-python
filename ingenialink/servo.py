import time
import threading
from enum import Enum

from ._ingenialink import ffi, lib
from .constants import DEFAULT_DRIVE_NAME
from ingenialink.exceptions import ILIOError

import ingenialogger

logger = ingenialogger.get_logger(__name__)


class SERVO_STATE(Enum):
    """Servo states."""
    NRDY = lib.IL_SERVO_STATE_NRDY
    """Not ready to switch on."""
    DISABLED = lib.IL_SERVO_STATE_DISABLED
    """Switch on disabled."""
    RDY = lib.IL_SERVO_STATE_RDY
    """Ready to be switched on."""
    ON = lib.IL_SERVO_STATE_ON
    """Power switched on."""
    ENABLED = lib.IL_SERVO_STATE_ENABLED
    """Enabled."""
    QSTOP = lib.IL_SERVO_STATE_QSTOP
    """Quick stop."""
    FAULTR = lib.IL_SERVO_STATE_FAULTR
    """Fault reactive."""
    FAULT = lib.IL_SERVO_STATE_FAULT
    """Fault."""


class SERVO_FLAGS(Enum):
    """Status Flags."""
    TGT_REACHED = lib.IL_SERVO_FLAG_TGT_REACHED
    """Target reached."""
    ILIM_ACTIVE = lib.IL_SERVO_FLAG_ILIM_ACTIVE
    """Internal limit active."""
    HOMING_ATT = lib.IL_SERVO_FLAG_HOMING_ATT
    """(Homing) attained."""
    HOMING_ERR = lib.IL_SERVO_FLAG_HOMING_ERR
    """(Homing) error."""
    PV_VZERO = lib.IL_SERVO_FLAG_PV_VZERO
    """(PV) Vocity speed is zero."""
    PP_SPACK = lib.IL_SERVO_FLAG_PP_SPACK
    """(PP) SP acknowledge."""
    IP_ACTIVE = lib.IL_SERVO_FLAG_IP_ACTIVE
    """(IP) active."""
    CS_FOLLOWS = lib.IL_SERVO_FLAG_CS_FOLLOWS
    """(CST/CSV/CSP) follow command value."""
    FERR = lib.IL_SERVO_FLAG_FERR
    """(CST/CSV/CSP/PV) following error."""
    IANGLE_DET = lib.IL_SERVO_FLAG_IANGLE_DET
    """Initial angle determination finished."""


class SERVO_MODE(Enum):
    """Operation Mode."""
    OLV = lib.IL_SERVO_MODE_OLV
    """Open loop (vector mode)."""
    OLS = lib.IL_SERVO_MODE_OLS
    """Open loop (scalar mode)."""
    PP = lib.IL_SERVO_MODE_PP
    """Profile position mode."""
    VEL = lib.IL_SERVO_MODE_VEL
    """Velocity mode."""
    PV = lib.IL_SERVO_MODE_PV
    """Profile velocity mode."""
    PT = lib.IL_SERVO_MODE_PT
    """Profile torque mode."""
    HOMING = lib.IL_SERVO_MODE_HOMING
    """Homing mode."""
    IP = lib.IL_SERVO_MODE_IP
    """Interpolated position mode."""
    CSP = lib.IL_SERVO_MODE_CSP
    """Cyclic sync position mode."""
    CSV = lib.IL_SERVO_MODE_CSV
    """Cyclic sync velocity mode."""
    CST = lib.IL_SERVO_MODE_CST
    """Cyclic sync torque mode."""


class SERVO_UNITS_TORQUE(Enum):
    """Torque Units."""
    NATIVE = lib.IL_UNITS_TORQUE_NATIVE
    """Native"""
    MN = lib.IL_UNITS_TORQUE_MNM
    """Millinewtons*meter."""
    N = lib.IL_UNITS_TORQUE_NM
    """Newtons*meter."""


class SERVO_UNITS_POS(Enum):
    """Position Units."""
    NATIVE = lib.IL_UNITS_POS_NATIVE
    """Native."""
    REV = lib.IL_UNITS_POS_REV
    """Revolutions."""
    RAD = lib.IL_UNITS_POS_RAD
    """Radians."""
    DEG = lib.IL_UNITS_POS_DEG
    """Degrees."""
    UM = lib.IL_UNITS_POS_UM
    """Micrometers."""
    MM = lib.IL_UNITS_POS_MM
    """Millimeters."""
    M = lib.IL_UNITS_POS_M
    """Meters."""


class SERVO_UNITS_VEL(Enum):
    """Velocity Units."""
    NATIVE = lib.IL_UNITS_VEL_NATIVE
    """Native."""
    RPS = lib.IL_UNITS_VEL_RPS
    """Revolutions per second."""
    RPM = lib.IL_UNITS_VEL_RPM
    """Revolutions per minute."""
    RAD_S = lib.IL_UNITS_VEL_RAD_S
    """Radians/second."""
    DEG_S = lib.IL_UNITS_VEL_DEG_S
    """Degrees/second."""
    UM_S = lib.IL_UNITS_VEL_UM_S
    """Micrometers/second."""
    MM_S = lib.IL_UNITS_VEL_MM_S
    """Millimeters/second."""
    M_S = lib.IL_UNITS_VEL_M_S
    """Meters/second."""


class SERVO_UNITS_ACC(Enum):
    """Acceleration Units."""
    NATIVE = lib.IL_UNITS_ACC_NATIVE
    """Native."""
    REV_S2 = lib.IL_UNITS_ACC_REV_S2
    """Revolutions/second^2."""
    RAD_S2 = lib.IL_UNITS_ACC_RAD_S2
    """Radians/second^2."""
    DEG_S2 = lib.IL_UNITS_ACC_DEG_S2
    """Degrees/second^2."""
    UM_S2 = lib.IL_UNITS_ACC_UM_S2
    """Micrometers/second^2."""
    MM_S2 = lib.IL_UNITS_ACC_MM_S2
    """Millimeters/second^2."""
    M_S2 = lib.IL_UNITS_ACC_M_S2
    """Meters/second^2."""


class ServoStatusListener(threading.Thread):
    """Reads the status word to check if the drive is alive.

    Args:
        servo (Servo): Servo instance of the drive.

    """
    def __init__(self, servo):
        super(ServoStatusListener, self).__init__()
        self.__servo = servo
        self.__stop = False

    def run(self):
        """Checks if the drive is alive by reading the status word register"""
        while not self.__stop:
            for subnode in range(1, self.__servo.subnodes):
                try:
                    status_word = self.__servo.read(
                        self.__servo.STATUS_WORD_REGISTERS[subnode], subnode=subnode
                    )
                    state = self.__servo.status_word_decode(status_word)
                    self.__servo._set_state(state, subnode=subnode)
                except ILIOError as e:
                    logger.error("Error getting drive status. "
                                 "Exception : %s", e)
            time.sleep(1.5)

    def stop(self):
        """Stops the loop that reads the status word register"""
        self.__stop = True


class Servo:
    """Declaration of a general Servo object.

    Args:
        target (str, int): Target ID of the servo.
        servo_status_listener (bool): Toggle the listener of the servo for
            its status, errors, faults, etc.

    Raises:
        ILCreationError: If the servo cannot be created.

    """
    def __init__(self, target, servo_status_listener=False):
        self.target = target
        self._info = None
        self.name = DEFAULT_DRIVE_NAME
        prod_name = '' if self.dictionary.part_number is None \
            else self.dictionary.part_number
        self.full_name = f'{prod_name} {self.name} ({self.target})'
        """str: Obtains the servo full name."""
        self.units_torque = None
        """SERVO_UNITS_TORQUE: Torque units."""
        self.units_pos = None
        """SERVO_UNITS_POS: Position units."""
        self.units_vel = None
        """SERVO_UNITS_VEL: Velocity units."""
        self.units_acc = None
        """SERVO_UNITS_ACC: Acceleration units."""
        self.__state = {
            1: lib.IL_SERVO_STATE_NRDY,
            2: lib.IL_SERVO_STATE_NRDY,
            3: lib.IL_SERVO_STATE_NRDY
        }
        self.__observers_servo_state = []
        self.__listener_servo_status = None
        self.__monitoring_num_mapped_registers = 0
        self.__monitoring_channels_size = {}
        self.__monitoring_channels_dtype = {}
        self.__monitoring_data = []
        self.__processed_monitoring_data = []
        self.__disturbance_num_mapped_registers = 0
        self.__disturbance_channels_size = {}
        self.__disturbance_channels_dtype = {}
        self.__disturbance_data_size = 0
        self.__disturbance_data = bytearray()
        if servo_status_listener:
            self.start_status_listener()
        else:
            self.stop_status_listener()

    def start_status_listener(self):
        """Start listening for servo status events (SERVO_STATE)."""
        if self.__listener_servo_status is not None:
            return
        status_word = self.read(self.STATUS_WORD_REGISTERS[1])
        state = self.status_word_decode(status_word)
        self._set_state(state, 1)

        self.__listener_servo_status = ServoStatusListener(self)
        self.__listener_servo_status.start()

    def stop_status_listener(self):
        """Stop listening for servo status events (SERVO_STATE)."""
        if self.__listener_servo_status is None:
            return
        if self.__listener_servo_status.is_alive():
            self.__listener_servo_status.stop()
            self.__listener_servo_status.join()
        self.__listener_servo_status = None

    @property
    def dictionary(self):
        """Returns dictionary object"""
        return self._dictionary

    @property
    def full_name(self):
        """str: Drive full name."""
        return self.__full_name

    @full_name.setter
    def full_name(self, new_name):
        self.__full_name = new_name
