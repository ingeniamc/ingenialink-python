from enum import Enum

from ._ingenialink import ffi, lib
from ._utils import cstr, pstr, raise_null, raise_err, to_ms
from .registers import Register, REG_DTYPE, _get_reg_id
from .net import Network
from .dict_ import Dictionary


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


def lucky(prot, dict_f=None):
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

    r = lib.il_servo_lucky(prot.value, net__, servo__, dict_f)
    raise_err(r)

    net_ = ffi.cast('il_net_t *', net__[0])
    servo_ = ffi.cast('il_servo_t *', servo__[0])

    net = Network._from_existing(net_)
    servo = Servo._from_existing(servo_)

    return net, servo


@ffi.def_extern()
def _on_state_change_cb(ctx, state, flags):
    """ On state change callback shim. """

    cb = ffi.from_handle(ctx)
    cb(SERVO_STATE(state), flags)


@ffi.def_extern()
def _on_emcy_cb(ctx, code):
    """ On emergency callback shim. """

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
                 REG_DTYPE.FLOAT: ['float *', lib.il_servo_raw_read_float]}
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

    def __init__(self, net, servo_id, dict_f=None):
        dict_f = cstr(dict_f) if dict_f else ffi.NULL
        servo = lib.il_servo_create(net._net, servo_id, dict_f)
        raise_null(servo)

        self._servo = ffi.gc(servo, lib.il_servo_destroy)

        self._state_cb = {}
        self._emcy_cb = {}

    @classmethod
    def _from_existing(cls, servo):
        """ Create a new class instance from an existing servo. """

        inst = cls.__new__(cls)
        inst._servo = ffi.gc(servo, lib.il_servo_destroy)

        inst._state_cb = {}
        inst._emcy_cb = {}

        return inst

    def reset(self):
        """Reset.

        Notes:
            You may need to reconnect the network after reset.
        """

        r = lib.il_servo_reset(self._servo)
        raise_err(r)

    @property
    def state(self):
        """ tuple: Servo state and state flags. """

        state = ffi.new('il_servo_state_t *')
        flags = ffi.new('int *')

        lib.il_servo_state_get(self._servo, state, flags)

        return SERVO_STATE(state[0]), flags[0]

    def state_subscribe(self, cb):
        """ Subscribe to state changes.

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
        """ Unsubscribe from state changes.

            Args:
                slot (int): Assigned slot when subscribed.
        """

        lib.il_servo_state_unsubscribe(self._servo, slot)

        del self._state_cb[slot]

    def emcy_subscribe(self, cb):
        """ Subscribe to emergency messages.

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
        """ Unsubscribe from emergency messages.

            Args:
                slot (int): Assigned slot when subscribed.
        """

        lib.il_servo_emcy_unsubscribe(self._servo, slot)

        del self._emcy_cb[slot]

    @property
    def dict(self):
        """ Dictionary: Dictionary. """
        _dict = lib.il_servo_dict_get(self._servo)

        return Dictionary._from_dict(_dict) if _dict else None

    def dict_load(self, dict_f):
        """ Load dictionary.

            Args:
                dict_f (str): Dictionary.
        """

        r = lib.il_servo_dict_load(self._servo, cstr(dict_f))
        raise_err(r)

    @property
    def name(self):
        """ str: Name. """

        name = ffi.new('char []', lib.IL_SERVO_NAME_SZ)

        r = lib.il_servo_name_get(self._servo, name, ffi.sizeof(name))
        raise_err(r)

        return pstr(name)

    @name.setter
    def name(self, name):
        name_ = ffi.new('char []', cstr(name))

        r = lib.il_servo_name_set(self._servo, name_)
        raise_err(r)

    @property
    def info(self):
        """ dict: Servo information. """

        info = ffi.new('il_servo_info_t *')

        r = lib.il_servo_info_get(self._servo, info)
        raise_err(r)

        return {'serial': info.serial,
                'name': pstr(info.name),
                'sw_version': pstr(info.sw_version),
                'hw_variant': pstr(info.hw_variant),
                'prod_code': info.prod_code,
                'revision': info.revision}

    def store_all(self):
        """ Store all servo current parameters to the NVM. """

        r = lib.il_servo_store_all(self._servo)
        raise_err(r)

    def store_comm(self):
        """ Store all servo current communications to the NVM. """

        r = lib.il_servo_store_comm(self._servo)
        raise_err(r)

    def store_app(self):
        """ Store all servo current application parameters to the NVM. """

        r = lib.il_servo_store_app(self._servo)
        raise_err(r)

    def raw_read(self, reg):
        """ Raw read from servo.

            Args:
                reg (Register): Register.

            Returns:
                int: Otained value

            Raises:
                TypeError: If the register type is not valid.
        """

        if isinstance(reg, Register):
            _reg = reg
        elif isinstance(reg, str):
            _dict = self.dict
            if not _dict:
                raise ValueError('No dictionary loaded')

            _reg = _dict.regs[reg]
        else:
            raise TypeError('Invalid register')

        # obtain data pointer and function to call
        t, f = self._raw_read[_reg.dtype]
        v = ffi.new(t)

        r = f(self._servo, _reg._reg, ffi.NULL, v)
        raise_err(r)

        return v[0]

    def read(self, reg):
        """ Read from servo.

            Args:
                reg (str, Register): Register.

            Returns:
                float: Otained value

            Raises:
                TypeError: If the register type is not valid.
        """

        _reg, _id = _get_reg_id(reg)

        v = ffi.new('double *')
        r = lib.il_servo_read(self._servo, _reg, _id, v)
        raise_err(r)

        return v[0]

    def raw_write(self, reg, data, confirm=True):
        """ Raw write to servo.

            Args:
                reg (Register): Register.
                data (int): Data.
                confirm (bool, optional): Confirm write.

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

            _reg = _dict.regs[reg]
        else:
            raise TypeError('Invalid register')

        # auto cast floats if register is not float
        if isinstance(data, float) and _reg.dtype != REG_DTYPE.FLOAT:
            data = int(data)

        # obtain function to call
        f = self._raw_write[_reg.dtype]

        r = f(self._servo, _reg._reg, ffi.NULL, data, confirm)
        raise_err(r)

    def write(self, reg, data, confirm=True):
        """ Write to servo.

            Args:
                reg (Register): Register.
                data (int): Data.
                confirm (bool, optional): Confirm write.

            Raises:
                TypeError: If any of the arguments type is not valid or
                    unsupported.
        """

        _reg, _id = _get_reg_id(reg)

        r = lib.il_servo_write(self._servo, _reg, _id, data, confirm)
        raise_err(r)

    def units_update(self):
        """ Update units scaling factors.

            Notes:
                This must be called if any encoder parameter, rated torque or
                pole pitch are changed, otherwise, the readings conversions
                will not be correct.
        """

        r = lib.il_servo_units_update(self._servo)
        raise_err(r)

    def units_factor(self, reg):
        """ Obtain units scale factor for the given register.

            Args:
                reg (Register): Register.

            Returns:
                float: Scale factor for the given register.
        """

        return lib.il_servo_units_factor(self._servo, reg._reg)

    @property
    def units_torque(self):
        """ SERVO_UNITS_TORQUE: Torque units. """
        return SERVO_UNITS_TORQUE(lib.il_servo_units_torque_get(self._servo))

    @units_torque.setter
    def units_torque(self, units):
        lib.il_servo_units_torque_set(self._servo, units.value)

    @property
    def units_pos(self):
        """ SERVO_UNITS_POS: Position units. """
        return SERVO_UNITS_POS(lib.il_servo_units_pos_get(self._servo))

    @units_pos.setter
    def units_pos(self, units):
        lib.il_servo_units_pos_set(self._servo, units.value)

    @property
    def units_vel(self):
        """ SERVO_UNITS_VEL: Velocity units. """
        return SERVO_UNITS_VEL(lib.il_servo_units_vel_get(self._servo))

    @units_vel.setter
    def units_vel(self, units):
        lib.il_servo_units_vel_set(self._servo, units.value)

    @property
    def units_acc(self):
        """ SERVO_UNITS_ACC: Acceleration units. """
        return SERVO_UNITS_ACC(lib.il_servo_units_acc_get(self._servo))

    @units_acc.setter
    def units_acc(self, units):
        lib.il_servo_units_acc_set(self._servo, units.value)

    def disable(self):
        """ Disable PDS. """

        r = lib.il_servo_disable(self._servo)
        raise_err(r)

    def switch_on(self, timeout=2.):
        """ Switch on PDS.

            This function switches on the PDS but it does not enable the motor.
            For most application cases, you should only use the `enable`
            function.

            Args:
                timeout (int, float, optional): Timeout (s).
        """

        r = lib.il_servo_switch_on(self._servo, to_ms(timeout))
        raise_err(r)

    def enable(self, timeout=2.):
        """ Enable PDS.

            Args:
                timeout (int, float, optional): Timeout (s).
        """

        r = lib.il_servo_enable(self._servo, to_ms(timeout))
        raise_err(r)

    def fault_reset(self):
        """ Fault reset. """

        r = lib.il_servo_fault_reset(self._servo)
        raise_err(r)

    @property
    def mode(self):
        """ MODE: Operation mode. """

        mode = ffi.new('il_servo_mode_t *')

        r = lib.il_servo_mode_get(self._servo, mode)
        raise_err(r)

        return SERVO_MODE(mode[0])

    @mode.setter
    def mode(self, mode):
        r = lib.il_servo_mode_set(self._servo, mode.value)
        raise_err(r)

    def homing_start(self):
        """ Start the homing procedure. """

        r = lib.il_servo_homing_start(self._servo)
        raise_err(r)

    def homing_wait(self, timeout):
        """ Wait until homing completes.

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
        """ float: Open loop voltage (% relative to DC-bus, -1...1). """

        voltage = ffi.new('double *')
        r = lib.il_servo_ol_voltage_get(self._servo, voltage)
        raise_err(r)

        return voltage[0]

    @ol_voltage.setter
    def ol_voltage(self, voltage):
        """ Set the open loop voltage (% relative to DC-bus, -1...1). """

        r = lib.il_servo_ol_voltage_set(self._servo, voltage)
        raise_err(r)

    @property
    def ol_frequency(self):
        """ float: Open loop frequency (mHz). """

        frequency = ffi.new('double *')
        r = lib.il_servo_ol_frequency_get(self._servo, frequency)
        raise_err(r)

        return frequency[0]

    @ol_frequency.setter
    def ol_frequency(self, frequency):
        """ Set the open loop frequency (mHz). """

        r = lib.il_servo_ol_frequency_set(self._servo, frequency)
        raise_err(r)

    @property
    def torque(self):
        """ float: Actual torque. """

        torque = ffi.new('double *')
        r = lib.il_servo_torque_get(self._servo, torque)
        raise_err(r)

        return torque[0]

    @torque.setter
    def torque(self, torque):
        """ Set the target torque. """

        r = lib.il_servo_torque_set(self._servo, torque)
        raise_err(r)

    @property
    def position(self):
        """ float: Actual position. """

        position = ffi.new('double *')
        r = lib.il_servo_position_get(self._servo, position)
        raise_err(r)

        return position[0]

    @position.setter
    def position(self, pos):
        """ Set the target position.

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
        """ int: Position resolution (c/rev/s, c/ppitch/s). """

        res = ffi.new('uint32_t *')
        r = lib.il_servo_position_res_get(self._servo, res)
        raise_err(r)

        return res[0]

    @property
    def velocity(self):
        """ float: Actual velocity. """

        velocity = ffi.new('double *')
        r = lib.il_servo_velocity_get(self._servo, velocity)
        raise_err(r)

        return velocity[0]

    @velocity.setter
    def velocity(self, velocity):
        """ Set the target velocity. """

        r = lib.il_servo_velocity_set(self._servo, velocity)
        raise_err(r)

    @property
    def velocity_res(self):
        """ int: Velocity resolution (c/rev, c/ppitch). """

        res = ffi.new('uint32_t *')
        r = lib.il_servo_velocity_res_get(self._servo, res)
        raise_err(r)

        return res[0]

    def wait_reached(self, timeout):
        """ Wait until the servo does a target reach.

            Args:
                timeout (int, float): Timeout (s).
        """

        r = lib.il_servo_wait_reached(self._servo, to_ms(timeout))
        raise_err(r)
