from enum import Enum

from ._ingenialink import ffi, lib
from ingenialink.utils._utils import *
from .registers import Register, REG_DTYPE, dtype_size, REG_ACCESS
from .dict_ import Dictionary
from .net import Network, NET_PROT

from .const import *

import xml.etree.ElementTree as ET
from xml.dom import minidom
import time
import io


class SERVO_STATE(Enum):
    """ State. """

    NRDY = lib.IL_SERVO_STATE_NRDY
    """ Not ready to switch on. """
    DISABLED = lib.IL_SERVO_STATE_DISABLED
    """ Switch on disabled. """
    RDY = lib.IL_SERVO_STATE_RDY
    """ Ready to be switched on. """
    ON = lib.IL_SERVO_STATE_ON
    """ Power switched on. """
    ENABLED = lib.IL_SERVO_STATE_ENABLED
    """ Enabled. """
    QSTOP = lib.IL_SERVO_STATE_QSTOP
    """ Quick stop. """
    FAULTR = lib.IL_SERVO_STATE_FAULTR
    """ Fault reactive. """
    FAULT = lib.IL_SERVO_STATE_FAULT
    """ Fault. """


class SERVO_FLAGS(object):
    """ Status Flags. """

    TGT_REACHED = lib.IL_SERVO_FLAG_TGT_REACHED
    """ Target reached. """
    ILIM_ACTIVE = lib.IL_SERVO_FLAG_ILIM_ACTIVE
    """ Internal limit active. """
    HOMING_ATT = lib.IL_SERVO_FLAG_HOMING_ATT
    """ (Homing) attained. """
    HOMING_ERR = lib.IL_SERVO_FLAG_HOMING_ERR
    """ (Homing) error. """
    PV_VZERO = lib.IL_SERVO_FLAG_PV_VZERO
    """ (PV) Vocity speed is zero. """
    PP_SPACK = lib.IL_SERVO_FLAG_PP_SPACK
    """ (PP) SP acknowledge. """
    IP_ACTIVE = lib.IL_SERVO_FLAG_IP_ACTIVE
    """ (IP) active. """
    CS_FOLLOWS = lib.IL_SERVO_FLAG_CS_FOLLOWS
    """ (CST/CSV/CSP) follow command value. """
    FERR = lib.IL_SERVO_FLAG_FERR
    """ (CST/CSV/CSP/PV) following error. """
    IANGLE_DET = lib.IL_SERVO_FLAG_IANGLE_DET
    """ Initial angle determination finished. """


class SERVO_MODE(Enum):
    """ Operation Mode. """

    OLV = lib.IL_SERVO_MODE_OLV
    """ Open loop (vector mode). """
    OLS = lib.IL_SERVO_MODE_OLS
    """ Open loop (scalar mode). """
    PP = lib.IL_SERVO_MODE_PP
    """ Profile position mode. """
    VEL = lib.IL_SERVO_MODE_VEL
    """ Velocity mode. """
    PV = lib.IL_SERVO_MODE_PV
    """ Profile velocity mode. """
    PT = lib.IL_SERVO_MODE_PT
    """ Profile torque mode. """
    HOMING = lib.IL_SERVO_MODE_HOMING
    """ Homing mode. """
    IP = lib.IL_SERVO_MODE_IP
    """ Interpolated position mode. """
    CSP = lib.IL_SERVO_MODE_CSP
    """ Cyclic sync position mode. """
    CSV = lib.IL_SERVO_MODE_CSV
    """ Cyclic sync velocity mode. """
    CST = lib.IL_SERVO_MODE_CST
    """ Cyclic sync torque mode. """


class SERVO_UNITS_TORQUE(Enum):
    """ Torque Units. """

    NATIVE = lib.IL_UNITS_TORQUE_NATIVE
    """ Native """
    MN = lib.IL_UNITS_TORQUE_MNM
    """ Millinewtons*meter. """
    N = lib.IL_UNITS_TORQUE_NM
    """ Newtons*meter. """


class SERVO_UNITS_POS(Enum):
    """ Position Units. """

    NATIVE = lib.IL_UNITS_POS_NATIVE
    """ Native. """
    REV = lib.IL_UNITS_POS_REV
    """ Revolutions. """
    RAD = lib.IL_UNITS_POS_RAD
    """ Radians. """
    DEG = lib.IL_UNITS_POS_DEG
    """ Degrees. """
    UM = lib.IL_UNITS_POS_UM
    """ Micrometers. """
    MM = lib.IL_UNITS_POS_MM
    """ Millimeters. """
    M = lib.IL_UNITS_POS_M
    """ Meters. """


class SERVO_UNITS_VEL(Enum):
    """ Velocity Units. """

    NATIVE = lib.IL_UNITS_VEL_NATIVE
    """ Native. """
    RPS = lib.IL_UNITS_VEL_RPS
    """ Revolutions per second. """
    RPM = lib.IL_UNITS_VEL_RPM
    """ Revolutions per minute. """
    RAD_S = lib.IL_UNITS_VEL_RAD_S
    """ Radians/second. """
    DEG_S = lib.IL_UNITS_VEL_DEG_S
    """ Degrees/second. """
    UM_S = lib.IL_UNITS_VEL_UM_S
    """ Micrometers/second. """
    MM_S = lib.IL_UNITS_VEL_MM_S
    """ Millimeters/second. """
    M_S = lib.IL_UNITS_VEL_M_S
    """ Meters/second. """


class SERVO_UNITS_ACC(Enum):
    """ Acceleration Units. """

    NATIVE = lib.IL_UNITS_ACC_NATIVE
    """ Native. """
    REV_S2 = lib.IL_UNITS_ACC_REV_S2
    """ Revolutions/second^2. """
    RAD_S2 = lib.IL_UNITS_ACC_RAD_S2
    """ Radians/second^2. """
    DEG_S2 = lib.IL_UNITS_ACC_DEG_S2
    """ Degrees/second^2. """
    UM_S2 = lib.IL_UNITS_ACC_UM_S2
    """ Micrometers/second^2. """
    MM_S2 = lib.IL_UNITS_ACC_MM_S2
    """ Millimeters/second^2. """
    M_S2 = lib.IL_UNITS_ACC_M_S2
    """ Meters/second^2. """


@deprecated
def servo_is_connected(address_ip, port_ip=1061, protocol=1):
    """ Obtain boolean with result of search a servo into ip.

    Args:
        address_ip: IP Address.

    Returns:
        bool

    """
    net__ = ffi.new('il_net_t **')
    address_ip = cstr(address_ip) if address_ip else ffi.NULL
    return lib.il_servo_is_connected(net__, address_ip, port_ip, protocol)


@deprecated
def lucky(prot, dict_f=None, address_ip=None, port_ip=23, protocol=1):
    """ Obtain an instance of the first available Servo.

    Args:
        prot (NET_PROT): Network protocol.
        dict_f (str, optional): Dictionary.

    Returns:
        tuple:

            - Network: Servo network instance.
            - Servo: Servo instance.
    """
    net__ = ffi.new('il_net_t **')
    servo__ = ffi.new('il_servo_t **')
    dict_f = cstr(dict_f) if dict_f else ffi.NULL
    address_ip = cstr(address_ip) if address_ip else ffi.NULL

    if prot.value == 2:
        r = lib.il_servo_lucky_eth(prot.value, net__, servo__, dict_f,
                                   address_ip, port_ip, protocol)
    else:
        r = lib.il_servo_lucky(prot.value, net__, servo__, dict_f)
    raise_err(r)

    net_ = ffi.cast('il_net_t *', net__[0])
    servo_ = ffi.cast('il_servo_t *', servo__[0])

    net = Network._from_existing(net_)
    servo = Servo._from_existing(servo_, dict_f)
    servo.net = net

    return net, servo


@deprecated
def connect_ecat(ifname, dict_f, slave=1, use_eoe_comms=1):
    """ Connect the drive through SOEM communications.

    Args:
        ifname (str): Interface name.
        dict_f (str): Dictionary path.
        slave (int): Slave number.
        use_eoe_comms (int): Use of EoE communications or communicate via SDOs.

    Returns:
        tuple: Servo and Network.

    """
    net = Network(prot=NET_PROT.ECAT, slave=slave)
    servo = Servo(net=net, dict_f=dict_f)

    r = servo.connect_ecat(ifname=ifname,
                           slave=slave,
                           use_eoe_comms=use_eoe_comms)

    if r <= 0:
        servo = None
        net = None
        raise_err(r)
    else:
        net.__net = ffi.cast('il_net_t *', net.__net[0])
        servo.__servo_interface = ffi.cast('il_servo_t *', servo.__servo_interface[0])
        servo.net = net

    return servo, net


@ffi.def_extern()
def _on_state_change_cb(ctx, state, flags, subnode):
    """ On state change callback shim. """
    cb = ffi.from_handle(ctx)
    cb(SERVO_STATE(state), flags, subnode)


@ffi.def_extern()
def _on_emcy_cb(ctx, code):
    """ On emergency callback shim. """
    cb = ffi.from_handle(ctx)
    cb(code)


class Servo(object):
    """ Basic declaration of a common Servo object.

    Args:
        net (Network): Network instance.
        target (str, int): Target ID of the servo.
        dictionary (object):  Path to the dictionary file.

    Raises:
        ILCreationError: If the servo cannot be created.
    """

    _raw_read = {REG_DTYPE.U8: ['uint8_t *', lib.il_servo_raw_read_u8],
                 REG_DTYPE.S8: ['int8_t *', lib.il_servo_raw_read_s8],
                 REG_DTYPE.U16: ['uint16_t *', lib.il_servo_raw_read_u16],
                 REG_DTYPE.S16: ['int16_t *', lib.il_servo_raw_read_s16],
                 REG_DTYPE.U32: ['uint32_t *', lib.il_servo_raw_read_u32],
                 REG_DTYPE.S32: ['int32_t *', lib.il_servo_raw_read_s32],
                 REG_DTYPE.U64: ['uint64_t *', lib.il_servo_raw_read_u64],
                 REG_DTYPE.S64: ['int64_t *', lib.il_servo_raw_read_s64],
                 REG_DTYPE.FLOAT: ['float *', lib.il_servo_raw_read_float],
                 REG_DTYPE.STR: ['uint32_t *', lib.il_servo_raw_read_str]}
    """ dict: Data buffer and function mappings for raw read operation. """

    _raw_write = {REG_DTYPE.U8: lib.il_servo_raw_write_u8,
                  REG_DTYPE.S8: lib.il_servo_raw_write_s8,
                  REG_DTYPE.U16: lib.il_servo_raw_write_u16,
                  REG_DTYPE.S16: lib.il_servo_raw_write_s16,
                  REG_DTYPE.U32: lib.il_servo_raw_write_u32,
                  REG_DTYPE.S32: lib.il_servo_raw_write_s32,
                  REG_DTYPE.U64: lib.il_servo_raw_write_u64,
                  REG_DTYPE.S64: lib.il_servo_raw_write_s64,
                  REG_DTYPE.FLOAT: lib.il_servo_raw_write_float}
    """ dict: Function mappings for raw write operation. """

    def __init__(self, net, target, dictionary=None):
        self._dictionary = dictionary
        self.target = target
        self.net = net

        self.__name = DEFAULT_DRIVE_NAME
        self.__full_name = None
        self.__info = None
        self.__units_torque = None
        self.__units_pos = None
        self.__units_vel = None
        self.__units_acc = None
        self.__units_torque = None

    def is_alive(self):
        """ Checks if the servo is responding and thus, if it is still alive.

        Returns:
            bool: Indicating if the servo is alive or not.
        """
        raise NotImplementedError

    def get_state(self, subnode=1):
        """ Obtain state of the servo.

        Args:
            subnode (int, optional): Subnode.

        Returns:
            tuple: Servo state and state flags.
        """
        raise NotImplementedError

    def subscribe_to_servo_status(self, cb):
        """ Subscribe to state changes.

        Args:
            cb: Callback

        Returns:
            int: Assigned slot.
        """
        raise NotImplementedError

    def unsubscribe_to_servo_status(self, slot):
        """ Unsubscribe from state changes.

        Args:
            slot (int): Assigned slot when subscribed.
        """
        raise NotImplementedError

    def reload_errors(self, dictionary):
        """ Force to reload all dictionary errors.

        Args:
            dictionary (str): Dictionary.
        """
        raise NotImplementedError

    def load_configuration(self, dictionary, subnode=0):
        """ Load configuration from dictionary file to the servo drive.

        Args:
            dictionary (str): Dictionary.
            subnode (int, optional): Subnode.

        """
        raise NotImplementedError

    def save_configuration(self, new_path, subnode=0):
        """ Read all dictionary registers content and save it to a
            new dictionary.

        Args:
            new_path (str): Dictionary.

        """
        raise NotImplementedError

    def get_reg(self, reg, subnode):
        """ Obtain Register object and its identifier.

        Args:
            reg (Register, str): Register.
            subnode (int): Subnode.

        Returns:
            tuple (Register, string): Actual Register instance and its
                                        identifier.
        """
        raise NotImplementedError

    def read(self, reg, subnode=1):
        """ Read from servo.

        Args:
            reg (str, Register): Register.

        Returns:
            float: Obtained value

        Raises:
            TypeError: If the register type is not valid.
        """
        raise NotImplementedError

    def write(self, reg, data, confirm=True, extended=0, subnode=1):
        """ Write to servo.

        Args:
            reg (Register): Register.
            data (int): Data.
            confirm (bool, optional): Confirm write.
            extended (int, optional): Extended frame.

        Raises:
            TypeError: If any of the arguments type is not valid or
                unsupported.
        """
        raise NotImplementedError

    def disable(self, subnode=1):
        """ Disable PDS. """
        raise NotImplementedError

    def enable(self, timeout=2., subnode=1):
        """ Enable PDS.

        Args:
            timeout (int, float, optional): Timeout (s).
            subnode (int, optional): Subnode.
        """
        raise NotImplementedError

    def fault_reset(self, subnode=1):
        """ Fault reset.

        Args:
            subnode (int, optional): Subnode.
        """
        raise NotImplementedError

    @property
    def name(self):
        """ Obtain servo name.

        Returns:
            str: Name.
        """
        return self.__name

    @name.setter
    def name(self, name):
        """ Set servo name.

        Args:
            name (str): Name.
        """
        self.__name = name

    @property
    def full_name(self):
        """ Obtain servo full name.

        Returns:
            str: Name.
        """
        return self.__full_name

    @full_name.setter
    def full_name(self, name):
        """ Set servo full name.

        Args:
            name (str): Name.
        """
        self.__full_name = name

    @property
    def dictionary(self):
        """ Obtain dictionary of the servo. """
        return self._dictionary

    @dictionary.setter
    def dictionary(self, value):
        self._dictionary = value

    @property
    def info(self):
        """ Obtain servo information.

        Returns:
            dict: Servo information.
        """
        return self.__info

    @property
    def units_torque(self):
        """ Torque units. """
        return self.__units_torque

    @units_torque.setter
    def units_torque(self, units):
        self.__units_torque = units

    @property
    def units_pos(self):
        """ SERVO_UNITS_POS: Position units. """
        return self.__units_pos

    @units_pos.setter
    def units_pos(self, units):
        self.__units_pos = units

    @property
    def units_vel(self):
        """ SERVO_UNITS_VEL: Velocity units. """
        return self.__units_vel

    @units_vel.setter
    def units_vel(self, units):
        self.__units_vel = units

    @property
    def units_acc(self):
        """ SERVO_UNITS_ACC: Acceleration units. """
        return self.__units_acc

    @units_acc.setter
    def units_acc(self, units):
        self.__units_acc = units

    @property
    def errors(self):
        """ Obtain drive errors.

        Returns:
            dict: Current errors.
        """
        raise NotImplementedError

    @property
    def subnodes(self):
        """ Obtain number of subnodes.

        Returns:
            int: Current number of subnodes.
        """
        raise NotImplementedError

