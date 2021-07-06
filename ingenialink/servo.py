from enum import Enum

from ._ingenialink import ffi, lib
from ._utils import *
from .registers import Register, REG_DTYPE, dtype_size, REG_ACCESS
from .net import Network, NET_PROT
from .dict_ import Dictionary

from .const import *

import xml.etree.ElementTree as ET
from xml.dom import minidom
import time
import io


DIST_NUMBER_SAMPLES = Register(
    identifier='', units='', subnode=0, address=0x00C4, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RW, range=None
)
DIST_DATA = Register(
    identifier='', units='', subnode=0, address=0x00B4, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.WO, range=None
)


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


def servo_is_connected(address_ip, port_ip=1061, protocol=1):
    """
    Obtain boolean with result of search a servo into ip.

    Args:
        address_ip: IP Address.

    Returns:
        bool

    """
    net__ = ffi.new('il_net_t **')
    address_ip = cstr(address_ip) if address_ip else ffi.NULL
    return lib.il_servo_is_connected(net__, address_ip, port_ip, protocol)


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


def connect_ecat(ifname, dict_f, slave=1, use_eoe_comms=1):
    """
    Connect the drive through SOEM communications.

    Args:
        ifname: Interface name.
        dict_f: Dictionary path.
        slave: Slave number.
        use_eoe_comms: Use of EoE communications or communicate via SDOs.

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
        net._net = ffi.cast('il_net_t *', net._net[0])
        servo._servo = ffi.cast('il_servo_t *', servo._servo[0])
        servo.net = net

    return servo, net


@ffi.def_extern()
def _on_state_change_cb(ctx, state, flags, subnode):
    """
    On state change callback shim.
    """
    cb = ffi.from_handle(ctx)
    cb(SERVO_STATE(state), flags, subnode)


@ffi.def_extern()
def _on_emcy_cb(ctx, code):
    """
    On emergency callback shim.
    """
    cb = ffi.from_handle(ctx)
    cb(code)


class Servo(object):
    """ Servo.

        Args:
            net (Network): Network instance.
            id (int): Servo id.

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

    def __init__(self, net, servo_id=None, dict_f=None):
        self.dict_f = cstr(dict_f) if dict_f else ffi.NULL
        self.full_name = None

        if servo_id:
            servo = lib.il_servo_create(net._net, servo_id, self.dict_f)
            raise_null(servo)

            self._servo = ffi.gc(servo, lib.il_servo_destroy)
            self._net = net

        else:
            self._net = net
            self._servo = ffi.new('il_servo_t **')

        self._state_cb = {}
        self._emcy_cb = {}
        if not hasattr(self, '_errors') or not self._errors:
            self._errors = self._get_all_errors(self.dict_f)

    @classmethod
    def _from_existing(cls, servo, dict_f):
        """
        Create a new class instance from an existing servo.

        Args:
            servo (Servo): Servo instance.
            dict_f (str): Path to the dictionary file.

        Returns:
            Servo: Instance of servo.

        """
        inst = cls.__new__(cls)
        inst._servo = ffi.gc(servo, lib.il_servo_fake_destroy)

        inst._state_cb = {}
        inst._emcy_cb = {}
        if not hasattr(inst, '_errors') or not inst._errors:
            inst._errors = inst._get_all_errors(dict_f)

        return inst

    def connect_ecat(self, ifname, slave, use_eoe_comms):
        """
        Connect drive through SOEM communications.

        Args:
            ifname: Interface name.
            slave: Slave number.
            use_eoe_comms: Use of EoE communications or communicate via SDOs.

        Returns:
            int: Result code.

        """
        self.ifname = cstr(ifname) if ifname else ffi.NULL
        self.slave = slave

        r = lib.il_servo_connect_ecat(3, self.ifname, self.net._net, self._servo, self.dict_f, 1061, self.slave, use_eoe_comms)
        time.sleep(2)
        return r

    def _get_all_errors(self, dict_f):
        """
        Obtain all errors defined in the dictionary.

        Args:
            dict_f: Path to the dictionary file.

        Returns:
            dict: Current errors definde in the dictionary.
        """
        errors = dict()
        if str(dict_f) != "<cdata 'void *' NULL>":
            tree = ET.parse(dict_f)
            for error in tree.iter("Error"):
                label = error.find(".//Label")
                id = int(error.attrib['id'], 0)
                errors[id] = [
                    error.attrib['id'],
                    error.attrib['affected_module'],
                    error.attrib['error_type'].capitalize(),
                    label.text
                ]
        return errors

    def destroy(self):
        """
        Destroy servo instance.

        Returns:
            int: Result code.
        """
        r = lib.il_servo_destroy(self._servo)
        return r

    def reset(self):
        """
        Reset servo.

        Notes:
            You may need to reconnect the network after reset.
        """
        r = lib.il_servo_reset(self._servo)
        raise_err(r)

    def get_state(self, subnode=1):
        """
        Obtain state of the servo.

        Args:
            subnode (int, optional): Subnode.

        Returns:
            tuple: Servo state and state flags.
        """
        state = ffi.new('il_servo_state_t *')
        flags = ffi.new('int *')

        lib.il_servo_state_get(self._servo, state, flags, subnode)

        return SERVO_STATE(state[0]), flags[0]

    def state_subscribe(self, cb):
        """
        Subscribe to state changes.

        Args:
            cb: Callback

        Returns:
            int: Assigned slot.
        """
        cb_handle = ffi.new_handle(cb)

        slot = lib.il_servo_state_subscribe(
                self._servo, lib._on_state_change_cb, cb_handle)
        if slot < 0:
            raise_err(slot)

        self._state_cb[slot] = cb_handle

        return slot

    def state_unsubscribe(self, slot):
        """
        Unsubscribe from state changes.

        Args:
            slot (int): Assigned slot when subscribed.
        """
        lib.il_servo_state_unsubscribe(self._servo, slot)

        del self._state_cb[slot]

    def emcy_subscribe(self, cb):
        """
        Subscribe to emergency messages.

        Args:
            cb: Callback

        Returns:
            int: Assigned slot.
        """
        cb_handle = ffi.new_handle(cb)

        slot = lib.il_servo_emcy_subscribe(
                self._servo, lib._on_emcy_cb, cb_handle)
        if slot < 0:
            raise_err(slot)

        self._emcy_cb[slot] = cb_handle

        return slot

    def emcy_unsubscribe(self, slot):
        """
        Unsubscribe from emergency messages.

        Args:
            slot (int): Assigned slot when subscribed.
        """
        lib.il_servo_emcy_unsubscribe(self._servo, slot)

        del self._emcy_cb[slot]

    def state_subs_stop(self, stop):
        """
        Stop servo state subscriptions.

        Args:
            stop (int): start: 0, stop: 1.

        Returns:
            int: Result code.
        """
        return lib.il_servo_state_subs_stop(self._servo, stop)

    @property
    def errors(self):
        """
        Obtain drive errors.

        Returns:
            dict: Current errors.
        """
        return self._errors

    @property
    def net(self):
        """
        Obtain servo network.

        Returns:
            Network: Current servo network.
        """
        return self._net

    @net.setter
    def net(self, value):
        """
        Set servo network.

        Args:
            value (Network): Network to be setted as servo Network.
        """
        self._net = value

    @property
    def subnodes(self):
        """
        Obtain number of subnodes.

        Returns:
            int: Current number of subnodes.
        """
        return int(ffi.cast('int', lib.il_servo_subnodes_get(self._servo)))

    @property
    def dict(self):
        """
        Obtain dictionary of the servo.

        Returns:
            dict: Current dictionary of the servo.
        """
        _dict = lib.il_servo_dict_get(self._servo)

        return Dictionary._from_dict(_dict) if _dict else None

    def dict_load(self, dict_f):
        """
        Load dictionary.

        Args:
            dict_f (str): Dictionary.
        """
        r = lib.il_servo_dict_load(self._servo, cstr(dict_f))
        if not hasattr(self, '_errors') or not self._errors:
            self._errors = self._get_all_errors(dict_f)
        raise_err(r)

    def reload_errors(self, dict_f):
        """
        Force to reload all dictionary errors.

        Args:
            dict_f (str): Dictionary.
        """
        self._errors = self._get_all_errors(dict_f)

    def dict_storage_read(self, new_path, subnode=0):
        """
        Read all dictionary registers content and put it to the dictionary
        storage.

        Args:
            new_path (str): Dictionary.

        """
        r = lib.il_servo_dict_storage_read(self._servo)
        raise_err(r)

        self.dict.save(new_path)

        tree = ET.parse(new_path)
        xml_data = tree.getroot()

        body = xml_data.find('Body')
        device = xml_data.find('Body/Device')
        categories = xml_data.find('Body/Device/Categories')
        errors = xml_data.find('Body/Errors')

        registers_category = xml_data.find('Body/Device/Registers')
        registers = xml_data.findall('Body/Device/Registers/Register')
        if registers_category is None:
            registers_category = xml_data.find('Body/Device/Axes/Axis/Registers')
            registers = xml_data.findall('Body/Device/Axes/Axis/Registers/Register')

        for register in registers:
            if register.attrib['subnode'] != str(subnode) and subnode > 0 and register in registers_category:
                registers_category.remove(register)
            cleanup_register(register)

        device.remove(categories)
        body.remove(errors)

        image = xml_data.find('./DriveImage')
        if image is not None:
            xml_data.remove(image)

        xmlstr = minidom.parseString(ET.tostring(xml_data)).toprettyxml(indent="  ", newl='')

        config_file = io.open(new_path, "w", encoding='utf8')
        config_file.write(xmlstr)
        config_file.close()

    def dict_storage_write(self, dict_f, subnode=0):
        """
        Write current dictionary storage to the servo drive.

        Args:
            dict_f (str): Dictionary.
            subnode (int, optional): Subnode.

        """
        r = lib.il_servo_dict_storage_write(self._servo, cstr(dict_f), subnode)
        if not hasattr(self, '_errors') or not self._errors:
            self._errors = self._get_all_errors(dict_f)
        raise_err(r)

    @property
    def name(self):
        """
        Obtain servo name.

        Returns:
            str: Name.
        """
        name = ffi.new('char []', lib.IL_SERVO_NAME_SZ)

        r = lib.il_servo_name_get(self._servo, name, ffi.sizeof(name))
        raise_err(r)

        return pstr(name)

    @name.setter
    def name(self, name):
        """
        Set servo name.

        Args:
            name (str): Name.
        """
        name_ = ffi.new('char []', cstr(name))

        r = lib.il_servo_name_set(self._servo, name_)
        raise_err(r)

    @property
    def info(self):
        """
        Obtain servo information.

        Returns:
            dict: Servo information.
        """
        info = ffi.new('il_servo_info_t *')

        r = lib.il_servo_info_get(self._servo, info)
        raise_err(r)

        PRODUCT_ID_REG = Register(identifier='', address=0x06E1,
                                  dtype=REG_DTYPE.U32,
                                  access=REG_ACCESS.RO, cyclic='CONFIG',
                                  units='0')

        product_id = self.read(PRODUCT_ID_REG)

        return {'serial': info.serial,
                'name': pstr(info.name),
                'sw_version': pstr(info.sw_version),
                'hw_variant': pstr(info.hw_variant),
                'prod_code': product_id,
                'revision': info.revision}

    def store_all(self, subnode=1):
        """
        Store all servo current parameters to the NVM.

        Args:
            subnode (int, optional): Subnode.
        """
        r = lib.il_servo_store_all(self._servo, subnode)
        raise_err(r)

    def store_comm(self):
        """
        Store all servo current communications to the NVM.
        """
        r = lib.il_servo_store_comm(self._servo)
        raise_err(r)

    def store_app(self):
        """
        Store all servo current application parameters to the NVM.
        """
        r = lib.il_servo_store_app(self._servo)
        raise_err(r)

    def raw_read(self, reg, subnode=1):
        """
        Raw read from servo.

        Args:
            reg (Register): Register.

        Returns:
            int: Otained value

        Raises:
            TypeError: If the register type is not valid.
        """
        return self.read(reg, subnode=subnode)

    def get_reg(self, reg, subnode):
        """
        Obtain Register object and its identifier.

        Args:
            reg (Register, str): Register.
            subnode (int): Subnode.

        Returns:
            tuple (Register, string): Actual Register instance and its
                                        identifier.
        """
        _reg = ffi.NULL
        _id = ffi.NULL
        if isinstance(reg, Register):
            _reg = reg._reg
        elif isinstance(reg, str):
            _dict = self.dict
            if not _dict:
                raise ValueError('No dictionary loaded')
            if reg not in _dict.get_regs(subnode):
                raise_err(lib.IL_REGNOTFOUND, 'Register not found ({})'.format(reg))
            _reg = _dict.get_regs(subnode)[reg]._reg
        else:
            raise TypeError('Invalid register')
        return _reg, _id

    def read(self, reg, subnode=1):
        """
        Read from servo.

        Args:
            reg (str, Register): Register.

        Returns:
            float: Otained value

        Raises:
            TypeError: If the register type is not valid.
        """
        if isinstance(reg, Register):
            _reg = reg
        elif isinstance(reg, str):
            _dict = self.dict
            if not _dict:
                raise ValueError('No dictionary loaded')
            if reg not in _dict.get_regs(subnode):
                raise_err(lib.IL_REGNOTFOUND, 'Register not found ({})'.format(reg))
            _reg = _dict.get_regs(subnode)[reg]
        else:
            raise TypeError('Invalid register')

        # obtain data pointer and function to call
        t, f = self._raw_read[_reg.dtype]
        v = ffi.new(t)

        r = f(self._servo, _reg._reg, ffi.NULL, v)
        raise_err(r)

        try:
            if self.dict:
                _reg = self.dict.get_regs(subnode)[reg]
        except Exception as e:
            pass
        if _reg.dtype == REG_DTYPE.STR:
            value =  self._net.extended_buffer
        else:
            value = v[0]

        if isinstance(value, str):
            value = value.replace('\x00', '')
        return  value

    def raw_write(self, reg, data, confirm=True, extended=0, subnode=1):
        """
        Raw write to servo.

        Args:
            reg (Register): Register.
            data (int): Data.
            confirm (bool, optional): Confirm write.
            extended (int, optional): Extended frame.

        Raises:
            TypeError: If any of the arguments type is not valid or
                unsupported.
        """
        self.write(reg, data, confirm, extended, subnode)

    def write(self, reg, data, confirm=True, extended=0, subnode=1):
        """
        Write to servo.

        Args:
            reg (Register): Register.
            data (int): Data.
            confirm (bool, optional): Confirm write.
            extended (int, optional): Extended frame.

        Raises:
            TypeError: If any of the arguments type is not valid or
                unsupported.
        """
        if isinstance(reg, Register):
            _reg = reg
        elif isinstance(reg, str):
            _dict = self.dict
            if not _dict:
                raise ValueError('No dictionary loaded')
            if reg not in _dict.get_regs(subnode):
                raise_err(lib.IL_REGNOTFOUND, 'Register not found ({})'.format(reg))
            _reg = _dict.get_regs(subnode)[reg]
        else:
            raise TypeError('Invalid register')

        # auto cast floats if register is not float
        if isinstance(data, float) and _reg.dtype != REG_DTYPE.FLOAT:
            data = int(data)

        # obtain function to call
        f = self._raw_write[_reg.dtype]

        r = f(self._servo, _reg._reg, ffi.NULL, data, confirm, extended)
        raise_err(r)

    def units_update(self):
        """
        Update units scaling factors.

        Notes:
            This must be called if any encoder parameter, rated torque or
            pole pitch are changed, otherwise, the readings conversions
            will not be correct.
        """
        r = lib.il_servo_units_update(self._servo)
        raise_err(r)

    def units_factor(self, reg):
        """
        Obtain units scale factor for the given register.

        Args:
            reg (Register): Register.

        Returns:
            float: Scale factor for the given register.
        """
        return lib.il_servo_units_factor(self._servo, reg._reg)

    @property
    def units_torque(self):
        """
        SERVO_UNITS_TORQUE: Torque units.
        """
        return SERVO_UNITS_TORQUE(lib.il_servo_units_torque_get(self._servo))

    @units_torque.setter
    def units_torque(self, units):
        lib.il_servo_units_torque_set(self._servo, units.value)

    @property
    def units_pos(self):
        """
        SERVO_UNITS_POS: Position units.
        """
        return SERVO_UNITS_POS(lib.il_servo_units_pos_get(self._servo))

    @units_pos.setter
    def units_pos(self, units):
        lib.il_servo_units_pos_set(self._servo, units.value)

    @property
    def units_vel(self):
        """
        SERVO_UNITS_VEL: Velocity units.
        """
        return SERVO_UNITS_VEL(lib.il_servo_units_vel_get(self._servo))

    @units_vel.setter
    def units_vel(self, units):
        lib.il_servo_units_vel_set(self._servo, units.value)

    @property
    def units_acc(self):
        """
        SERVO_UNITS_ACC: Acceleration units.
        """
        return SERVO_UNITS_ACC(lib.il_servo_units_acc_get(self._servo))

    @units_acc.setter
    def units_acc(self, units):
        lib.il_servo_units_acc_set(self._servo, units.value)

    def disable(self, subnode=1):
        """
        Disable PDS.

        """
        r = lib.il_servo_disable(self._servo, subnode)
        raise_err(r)

    def switch_on(self, timeout=2.):
        """
        Switch on PDS.

        This function switches on the PDS but it does not enable the motor.
        For most application cases, you should only use the `enable`
        function.

        Args:
            timeout (int, float, optional): Timeout (s).
        """
        r = lib.il_servo_switch_on(self._servo, to_ms(timeout))
        raise_err(r)

    def enable(self, timeout=2., subnode=1):
        """
        Enable PDS.

        Args:
            timeout (int, float, optional): Timeout (s).
            subnode (int, optional): Subnode.
        """
        r = lib.il_servo_enable(self._servo, to_ms(timeout), subnode)
        raise_err(r)

    def fault_reset(self, subnode=1):
        """
        Fault reset.

        Args:
            subnode (int, optional): Subnode.
        """
        r = lib.il_servo_fault_reset(self._servo, subnode)
        raise_err(r)

    @property
    def mode(self):
        """
        Obtains Operation mode.

        Returns:
            SERVO_MODE: Current operation mode.
        """
        mode = ffi.new('il_servo_mode_t *')

        r = lib.il_servo_mode_get(self._servo, mode)
        raise_err(r)

        return SERVO_MODE(mode[0])

    @mode.setter
    def mode(self, mode):
        """
        Set Operation mode.

        Args:
            mode (SERVO_MODE): Operation mode.
        """
        r = lib.il_servo_mode_set(self._servo, mode.value)
        raise_err(r)

    def homing_start(self):
        """
        Start the homing procedure.
        """
        r = lib.il_servo_homing_start(self._servo)
        raise_err(r)

    def homing_wait(self, timeout):
        """
        Wait until homing completes.

        Notes:
            The homing itself has a configurable timeout. The timeout given
            here is purely a 'communications' timeout, e.g. it could happen
            that the statusword change is never received. This timeout
            should be >= than the programmed homing timeout.

        Args:
            timeout (int, float): Timeout (s).
        """
        r = lib.il_servo_homing_wait(self._servo, to_ms(timeout))
        raise_err(r)

    @property
    def ol_voltage(self):
        """
        Get open loop voltage.

        Returns:
            float: Open loop voltage (% relative to DC-bus, -1...1).
        """
        voltage = ffi.new('double *')
        r = lib.il_servo_ol_voltage_get(self._servo, voltage)
        raise_err(r)

        return voltage[0]

    @ol_voltage.setter
    def ol_voltage(self, voltage):
        """
        Set the open loop voltage (% relative to DC-bus, -1...1).

        Args:
            float: Open loop voltage.
        """
        r = lib.il_servo_ol_voltage_set(self._servo, voltage)
        raise_err(r)

    @property
    def ol_frequency(self):
        """
        Get open loop frequency.

        Returns:
            float: Open loop frequency (mHz).
        """
        frequency = ffi.new('double *')
        r = lib.il_servo_ol_frequency_get(self._servo, frequency)
        raise_err(r)

        return frequency[0]

    @ol_frequency.setter
    def ol_frequency(self, frequency):
        """
        Set the open loop frequency (mHz).

        Args:
            float: Open loop frequency.
        """
        r = lib.il_servo_ol_frequency_set(self._servo, frequency)
        raise_err(r)

    @property
    def torque(self):
        """
        Get actual torque.

        Returns:
            float: Actual torque.
        """
        torque = ffi.new('double *')
        r = lib.il_servo_torque_get(self._servo, torque)
        raise_err(r)

        return torque[0]

    @torque.setter
    def torque(self, torque):
        """
        Set the target torque.

        Args:
            float: Target torque.
        """
        r = lib.il_servo_torque_set(self._servo, torque)
        raise_err(r)

    @property
    def position(self):
        """
        Get actual position.

        Returns:
            float: Actual position.
        """
        position = ffi.new('double *')
        r = lib.il_servo_position_get(self._servo, position)
        raise_err(r)

        return position[0]

    @position.setter
    def position(self, pos):
        """
        Set the target position.

        Notes:
            Position can be either a single position, or a tuple/list
            containing in the first position the position, and in the
            second a dictionary with the following options:

                - immediate (bool): If True, the servo will go to the
                  position immediately, otherwise it will push the position
                  to the buffer. Defaults to True.
                - relative (bool): If True, the position will be taken as
                  relative, otherwise it will be taken as absolute.
                  Defaults to False.
                - sp_timeout (int, float): Set-point acknowledge
                  timeout (s).

        Args:
            float: Target postion.
        """
        immediate = 1
        relative = 0
        sp_timeout = lib.IL_SERVO_SP_TIMEOUT_DEF

        if isinstance(pos, (tuple, list)):
            if len(pos) != 2 or not isinstance(pos[1], dict):
                raise TypeError('Unexpected position')

            if 'immediate' in pos[1]:
                immediate = int(pos[1]['immediate'])

            if 'relative' in pos[1]:
                relative = int(pos[1]['relative'])

            if 'sp_timeout' in pos[1]:
                sp_timeout = to_ms(pos[1]['sp_timeout'])

            pos = pos[0]

        r = lib.il_servo_position_set(self._servo, pos, immediate, relative,
                                      sp_timeout)
        raise_err(r)

    @property
    def position_res(self):
        """
        Get postion resolution.

        Returns:
            int: Position resolution (c/rev/s, c/ppitch/s).
        """
        res = ffi.new('uint32_t *')
        r = lib.il_servo_position_res_get(self._servo, res)
        raise_err(r)

        return res[0]

    @property
    def velocity(self):
        """
        Get actual velocity.

        Returns:
            float: Actual velocity.
        """
        velocity = ffi.new('double *')
        r = lib.il_servo_velocity_get(self._servo, velocity)
        raise_err(r)

        return velocity[0]

    @velocity.setter
    def velocity(self, velocity):
        """
        Set the target velocity.

        Args:
            float: Target velocity.
        """
        r = lib.il_servo_velocity_set(self._servo, velocity)
        raise_err(r)

    @property
    def velocity_res(self):
        """
        Get velocity resolution.

        Returns:
            int: Velocity resolution (c/rev, c/ppitch).
        """
        res = ffi.new('uint32_t *')
        r = lib.il_servo_velocity_res_get(self._servo, res)
        raise_err(r)

        return res[0]

    def wait_reached(self, timeout):
        """
        Wait until the servo does a target reach.

        Args:
            timeout (int, float): Timeout (s).
        """
        r = lib.il_servo_wait_reached(self._servo, to_ms(timeout))
        raise_err(r)

    def disturbance_write_data(self, channels, dtypes, data_arr):
        """
        Write disturbance data.

        Args:
            channels (int or list of int): Channel identifier.
            dtypes (int or list of int): Data type.
            data_arr (list or list of list): Data array.
        """
        if not isinstance(channels, list):
            channels = [channels]
        if not isinstance(dtypes, list):
            dtypes = [dtypes]
        if not isinstance(data_arr[0], list):
            data_arr = [data_arr]
        num_samples = len(data_arr[0])
        self.write(DIST_NUMBER_SAMPLES, num_samples, subnode=0)
        sample_size = 0
        for dtype_val in dtypes:
            sample_size += dtype_size(dtype_val)
        samples_for_write = DIST_FRAME_SIZE // sample_size
        number_writes = num_samples // samples_for_write
        rest_samples = num_samples % samples_for_write
        for i in range(number_writes):
            for index, channel in enumerate(channels):
                self.net.disturbance_channel_data(
                    channel,
                    dtypes[index],
                    data_arr[index][i*samples_for_write:(i+1)*samples_for_write])
            self.net.disturbance_data_size = sample_size*samples_for_write
            self.write(DIST_DATA, sample_size*samples_for_write, False, 1, subnode=0)
        for index, channel in enumerate(channels):
            self.net.disturbance_channel_data(
                channel,
                dtypes[index],
                data_arr[index][number_writes*samples_for_write:num_samples])
        self.net.disturbance_data_size = rest_samples * sample_size
        self.write(DIST_DATA, rest_samples * sample_size, False, 1, subnode=0)
