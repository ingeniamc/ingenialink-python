from ._ingenialink import ffi, lib
from ._utils import _cstr, _pstr
from . import exceptions as exc


__version__ = '3.5.1'


DTYPE_U8 = lib.IL_REG_DTYPE_U8
""" int: Unsigned 8-bit integer type. """
DTYPE_S8 = lib.IL_REG_DTYPE_S8
""" int: Signed 8-bit integer type. """
DTYPE_U16 = lib.IL_REG_DTYPE_U16
""" int: Unsigned 16-bit integer type. """
DTYPE_S16 = lib.IL_REG_DTYPE_S16
""" int: Signed 16-bit integer type. """
DTYPE_U32 = lib.IL_REG_DTYPE_U32
""" int: Unsigned 32-bit integer type. """
DTYPE_S32 = lib.IL_REG_DTYPE_S32
""" int: Signed 32-bit integer type. """
DTYPE_U64 = lib.IL_REG_DTYPE_U64
""" int: Unsigned 64-bit integer type. """
DTYPE_S64 = lib.IL_REG_DTYPE_S64
""" int: Signed 64-bit integer type. """

_DTYPE_ALL = (DTYPE_U8, DTYPE_S8, DTYPE_U16, DTYPE_S16, DTYPE_U32, DTYPE_S32,
              DTYPE_U64, DTYPE_S64)
""" tuple: All data types. """

ACCESS_RW = lib.IL_REG_ACCESS_RW
""" int: Read/Write access. """
ACCESS_RO = lib.IL_REG_ACCESS_RO
""" int: Read-only access. """
ACCESS_WO = lib.IL_REG_ACCESS_WO
""" int: Write-only access. """

_ACCESS_ALL = (ACCESS_RW, ACCESS_RO, ACCESS_WO)
""" tuple: All access types. """

PHY_NONE = lib.IL_REG_PHY_NONE
""" int: No phyisical units. """
PHY_TORQUE = lib.IL_REG_PHY_TORQUE
""" int: Torque units. """
PHY_POS = lib.IL_REG_PHY_POS
""" int: Position units. """
PHY_VEL = lib.IL_REG_PHY_VEL
""" int: Velocity units. """
PHY_ACC = lib.IL_REG_PHY_ACC
""" int: Acceleration units. """
PHY_VOLT_REL = lib.IL_REG_PHY_VOLT_REL
""" int: Relative voltage (DC) units. """

_PHY_ALL = (PHY_NONE, PHY_TORQUE, PHY_POS, PHY_VEL, PHY_ACC, PHY_VOLT_REL)
""" tuple: All physical units. """

STATE_NRDY = lib.IL_SERVO_STATE_NRDY
""" int: PDS state, Not ready to switch on. """
STATE_DISABLED = lib.IL_SERVO_STATE_DISABLED
""" int: PDS state, Switch on disabled. """
STATE_RDY = lib.IL_SERVO_STATE_RDY
""" int: PDS state, Ready to be switched on. """
STATE_ON = lib.IL_SERVO_STATE_ON
""" int: PDS state, Power switched on. """
STATE_ENABLED = lib.IL_SERVO_STATE_ENABLED
""" int: PDS state, Enabled. """
STATE_QSTOP = lib.IL_SERVO_STATE_QSTOP
""" int: PDS state, Quick stop. """
STATE_FAULTR = lib.IL_SERVO_STATE_FAULTR
""" int: PDS state, Fault reactive. """
STATE_FAULT = lib.IL_SERVO_STATE_FAULT
""" int: PDS state, Fault. """

FLAG_TGT_REACHED = lib.IL_SERVO_FLAG_TGT_REACHED
""" int: Flags, Target reached. """
FLAG_ILIM_ACTIVE = lib.IL_SERVO_FLAG_ILIM_ACTIVE
""" int: Flags, Internal limit active. """
FLAG_HOMING_ATT = lib.IL_SERVO_FLAG_HOMING_ATT
""" int: Flags, (Homing) attained. """
FLAG_HOMING_ERR = lib.IL_SERVO_FLAG_HOMING_ERR
""" int: Flags, (Homing) error. """
FLAG_PV_VZERO = lib.IL_SERVO_FLAG_PV_VZERO
""" int: Flags, (PV) Vocity speed is zero. """
FLAG_PP_SPACK = lib.IL_SERVO_FLAG_PP_SPACK
""" int: Flags, (PP) SP acknowledge. """
FLAG_IP_ACTIVE = lib.IL_SERVO_FLAG_IP_ACTIVE
""" int: Flags, (IP) active. """
FLAG_CS_FOLLOWS = lib.IL_SERVO_FLAG_CS_FOLLOWS
""" int: Flags, (CST/CSV/CSP) follow command value. """
FLAG_FERR = lib.IL_SERVO_FLAG_FERR
""" int: Flags, (CST/CSV/CSP/PV) following error. """
FLAG_IANGLE_DET = lib.IL_SERVO_FLAG_IANGLE_DET
""" int: Flags, Initial angle determination finished. """

MODE_OLV = lib.IL_SERVO_MODE_OLV
""" int: Open loop (vector mode). """
MODE_OLS = lib.IL_SERVO_MODE_OLS
""" int: Open loop (scalar mode). """
MODE_PP = lib.IL_SERVO_MODE_PP
""" int: Profile position mode. """
MODE_VEL = lib.IL_SERVO_MODE_VEL
""" int: Velocity mode. """
MODE_PV = lib.IL_SERVO_MODE_PV
""" int: Profile velocity mode. """
MODE_PT = lib.IL_SERVO_MODE_PT
""" int: Profile torque mode. """
MODE_HOMING = lib.IL_SERVO_MODE_HOMING
""" int: Homing mode. """
MODE_IP = lib.IL_SERVO_MODE_IP
""" int: Interpolated position mode. """
MODE_CSP = lib.IL_SERVO_MODE_CSP
""" int: Cyclic sync position mode. """
MODE_CSV = lib.IL_SERVO_MODE_CSV
""" int: Cyclic sync velocity mode. """
MODE_CST = lib.IL_SERVO_MODE_CST
""" int: Cyclic sync torque mode. """

_MODE_ALL = (MODE_OLV, MODE_OLS, MODE_PP, MODE_VEL, MODE_PV, MODE_PT,
             MODE_HOMING, MODE_IP, MODE_CSP, MODE_CSV, MODE_CST)
""" tuple: All operation modes. """

UNITS_TORQUE_NATIVE = lib.IL_UNITS_TORQUE_NATIVE
""" int: Torque units, Native """
UNITS_TORQUE_MN = lib.IL_UNITS_TORQUE_MN
""" int: Torque units, Millinewtons. """
UNITS_TORQUE_N = lib.IL_UNITS_TORQUE_N
""" int: Torque units, Newtons. """

_UNITS_TORQUE_ALL = (UNITS_TORQUE_NATIVE, UNITS_TORQUE_MN, UNITS_TORQUE_N)
""" tuple: All torque units. """

UNITS_POS_NATIVE = lib.IL_UNITS_POS_NATIVE
""" int: Position units, Native. """
UNITS_POS_REV = lib.IL_UNITS_POS_REV
""" int: Position units, Revolutions. """
UNITS_POS_RAD = lib.IL_UNITS_POS_RAD
""" int: Position units, Radians. """
UNITS_POS_DEG = lib.IL_UNITS_POS_DEG
""" int: Position units, Degrees. """
UNITS_POS_UM = lib.IL_UNITS_POS_UM
""" int: Position units, Micrometers. """
UNITS_POS_MM = lib.IL_UNITS_POS_MM
""" int: Position units, Millimeters. """
UNITS_POS_M = lib.IL_UNITS_POS_M
""" int: Position units, Meters. """

_UNITS_POS_ALL = (UNITS_POS_NATIVE, UNITS_POS_REV, UNITS_POS_RAD,
                  UNITS_POS_DEG, UNITS_POS_UM, UNITS_POS_MM, UNITS_POS_M)
""" tuple: All position units. """

UNITS_VEL_NATIVE = lib.IL_UNITS_VEL_NATIVE
""" int: Velocity units, Native. """
UNITS_VEL_RPS = lib.IL_UNITS_VEL_RPS
""" int: Velocity units, Revolutions per second. """
UNITS_VEL_RPM = lib.IL_UNITS_VEL_RPM
""" int: Velocity units, Revolutions per minute. """
UNITS_VEL_RAD_S = lib.IL_UNITS_VEL_RAD_S
""" int: Velocity units, Radians/second. """
UNITS_VEL_DEG_S = lib.IL_UNITS_VEL_DEG_S
""" int: Velocity units, Degrees/second. """
UNITS_VEL_UM_S = lib.IL_UNITS_VEL_UM_S
""" int: Velocity units, Micrometers/second. """
UNITS_VEL_MM_S = lib.IL_UNITS_VEL_MM_S
""" int: Velocity units, Millimeters/second. """
UNITS_VEL_M_S = lib.IL_UNITS_VEL_M_S
""" int: Velocity units, Meters/second. """

_UNITS_VEL_ALL = (UNITS_VEL_NATIVE, UNITS_VEL_RPS, UNITS_VEL_RPM,
                  UNITS_VEL_RAD_S, UNITS_VEL_DEG_S, UNITS_VEL_UM_S,
                  UNITS_VEL_MM_S, UNITS_VEL_M_S)
""" tuple: All velocity units. """

UNITS_ACC_NATIVE = lib.IL_UNITS_ACC_NATIVE
""" int: Acceleration units, Native. """
UNITS_ACC_REV_S2 = lib.IL_UNITS_ACC_REV_S2
""" int: Acceleration units, Revolutions/second^2. """
UNITS_ACC_RAD_S2 = lib.IL_UNITS_ACC_RAD_S2
""" int: Acceleration units, Radians/second^2. """
UNITS_ACC_DEG_S2 = lib.IL_UNITS_ACC_DEG_S2
""" int: Acceleration units, Degrees/second^2. """
UNITS_ACC_UM_S2 = lib.IL_UNITS_ACC_UM_S2
""" int: Acceleration units, Micrometers/second^2. """
UNITS_ACC_MM_S2 = lib.IL_UNITS_ACC_MM_S2
""" int: Acceleration units, Millimeters/second^2. """
UNITS_ACC_M_S2 = lib.IL_UNITS_ACC_M_S2
""" int: Acceleration units, Meters/second^2. """

_UNITS_ACC_ALL = (UNITS_ACC_NATIVE, UNITS_ACC_REV_S2, UNITS_ACC_RAD_S2,
                  UNITS_ACC_UM_S2, UNITS_ACC_DEG_S2, UNITS_ACC_MM_S2,
                  UNITS_ACC_M_S2)
""" tuple: All acceleration units. """

MONITOR_TRIGGER_IMMEDIATE = lib.IL_MONITOR_TRIGGER_IMMEDIATE
""" int: Monitor trigger, immediate. """
MONITOR_TRIGGER_MOTION = lib.IL_MONITOR_TRIGGER_MOTION
""" int: Monitor trigger, motion start. """
MONITOR_TRIGGER_POS = lib.IL_MONITOR_TRIGGER_POS
""" int: Monitor trigger, positive. """
MONITOR_TRIGGER_NEG = lib.IL_MONITOR_TRIGGER_NEG
""" int: Monitor trigger, negative. """
MONITOR_TRIGGER_WINDOW = lib.IL_MONITOR_TRIGGER_WINDOW
""" int: Monitor trigger, exit window. """
MONITOR_TRIGGER_DIN = lib.IL_MONITOR_TRIGGER_DIN
""" int: Monitor trigger, digital input. """

_MONITOR_TRIGGER_ALL = (MONITOR_TRIGGER_IMMEDIATE, MONITOR_TRIGGER_MOTION,
                        MONITOR_TRIGGER_POS, MONITOR_TRIGGER_NEG,
                        MONITOR_TRIGGER_WINDOW, MONITOR_TRIGGER_DIN)
""" tuple: All monitor triggers. """

NET_STATE_OPERATIVE = lib.IL_NET_STATE_OPERATIVE
""" int: Network state, operative. """
NET_STATE_FAULTY = lib.IL_NET_STATE_FAULTY
""" int: Network state, faulty. """

EVT_ADDED = 0
""" int: Device added event. """
EVT_REMOVED = 1
""" int: Device removed event. """

_raw_read = {DTYPE_U8: ['uint8_t *', lib.il_servo_raw_read_u8],
             DTYPE_S8: ['int8_t *', lib.il_servo_raw_read_s8],
             DTYPE_U16: ['uint16_t *', lib.il_servo_raw_read_u16],
             DTYPE_S16: ['int16_t *', lib.il_servo_raw_read_s16],
             DTYPE_U32: ['uint32_t *', lib.il_servo_raw_read_u32],
             DTYPE_S32: ['int32_t *', lib.il_servo_raw_read_s32],
             DTYPE_U64: ['uint64_t *', lib.il_servo_raw_read_u64],
             DTYPE_S64: ['int64_t *', lib.il_servo_raw_read_s64]}
""" dict: Data buffer and function mappings for raw read operation. """

_raw_write = {DTYPE_U8: lib.il_servo_raw_write_u8,
              DTYPE_S8: lib.il_servo_raw_write_s8,
              DTYPE_U16: lib.il_servo_raw_write_u16,
              DTYPE_S16: lib.il_servo_raw_write_s16,
              DTYPE_U32: lib.il_servo_raw_write_u32,
              DTYPE_S32: lib.il_servo_raw_write_s32,
              DTYPE_U64: lib.il_servo_raw_write_u64,
              DTYPE_S64: lib.il_servo_raw_write_s64}
""" dict: Function mappings for raw write operation. """


def _raise_null(obj):
    """ Raise exception if object is ffi.NULL.

        Raises:
            IngeniaLinkCreationError: If the object is NULL.
    """

    if obj == ffi.NULL:
        msg = _pstr(lib.ilerr_last())
        raise exc.IngeniaLinkCreationError(msg)


def _raise_err(code):
    """ Raise exception if the code is non-zero.

        Raises:
            IngeniaLinkValueError: if code is lib.IL_EINVAL
            IngeniaLinkTimeoutError: if code is lib.IL_ETIMEDOUT
            IngeniaLinkMemoryError: if code is lib.IL_ENOMEM
            IngeniaLinkFaultError: if code is lib.IL_EFAULT
            IngeniaLinkDisconnectionError: if code is lib.IL_EDISCONN
            IngeniaLinkAccessError: if code is lib.IL_EACCESS
            IngeniaLinkStateError: if code is lib.IL_ESTATE
            IngeniaLinkError: if code is lib.IL_EFAULT
    """

    if code == 0:
        return

    # obtain message and raise its matching exception
    msg = _pstr(lib.ilerr_last())

    if code == lib.IL_EINVAL:
        raise exc.IngeniaLinkValueError(msg)
    elif code == lib.IL_ETIMEDOUT:
        raise exc.IngeniaLinkTimeoutError(msg)
    elif code == lib.IL_ENOMEM:
        raise exc.IngeniaLinkMemoryError(msg)
    elif code == lib.IL_EDISCONN:
        raise exc.IngeniaLinkDisconnectionError(msg)
    elif code == lib.IL_EACCESS:
        raise exc.IngeniaLinkAccessError(msg)
    elif code == lib.IL_ESTATE:
        raise exc.IngeniaLinkStateError(msg)
    elif code == lib.IL_EIO:
        raise exc.IngeniaLinkIOError(msg)
    else:
        raise exc.IngeniaLinkError(msg)


class Register(object):
    """ IngeniaLink node register.

        Args:
            idx (int): Reigtser index.
            sidx (int): Register subindex.
            dtype (int): Register data type.
            access (int): Register access type.
            phy (int): Register physical units.

        Raises:
            ValueError: If the data type is unsupported.
    """

    def __init__(self, idx, sidx, dtype, access, phy):
        if dtype not in _DTYPE_ALL:
            raise ValueError('Unsupported register data type')

        if access not in _ACCESS_ALL:
            raise ValueError('Unsupported access type')

        if phy not in _PHY_ALL:
            raise ValueError('Unsupported phyisical units type')

        self._reg = ffi.new('il_reg_t *',
                            {'idx': idx,
                             'sidx': sidx,
                             'dtype': dtype,
                             'access': access,
                             'phy': phy})

    def __repr__(self):
        return '<Register (0x{:04x}, 0x{:02x})>'.format(self.idx, self.sidx)

    @classmethod
    def _from_register(cls, reg):
        """ Create a new class instance from an existing register. """

        inst = cls.__new__(cls)

        inst._reg_p = ffi.new('il_reg_t *', reg)
        inst._reg = inst._reg_p

        return inst

    @property
    def idx(self):
        """ int: Register index. """
        return self._reg.idx

    @property
    def sidx(self):
        """ int: Register subindex. """
        return self._reg.sidx

    @property
    def dtype(self):
        """ int: Register data type. """
        return self._reg.dtype

    @property
    def access(self):
        """ int: Register access type. """
        return self._reg.access

    @property
    def phy(self):
        """ int: Register physical units. """
        return self._reg.phy


def devices():
    """ Obtain a list of network devices.

        Returns:
            list: List of network devices.
    """

    devs = lib.il_net_dev_list_get()

    found = []
    curr = devs

    while curr:
        found.append(_pstr(curr.port))
        curr = curr.next

    lib.il_net_dev_list_destroy(devs)

    return found


def lucky():
    """ Obtain an instance of the first available Servo.

        Returns:
            tuple:

                - Network: Servo network instance.
                - Servo: Servo instance.
    """

    net__ = ffi.new('il_net_t **')
    servo__ = ffi.new('il_servo_t **')

    r = lib.il_servo_lucky(net__, servo__)
    _raise_err(r)

    net_ = ffi.cast('il_net_t *', net__[0])
    servo_ = ffi.cast('il_servo_t *', servo__[0])

    net = Network._from_existing(net_)
    servo = Servo._from_existing(servo_)

    return net, servo


@ffi.def_extern()
def _on_found_cb(ctx, servo_id):
    """ On found callback shim. """

    self = ffi.from_handle(ctx)
    self._on_found(int(servo_id))


class Network(object):
    """ IngeniaLink network.

        Args:
            port (str): Network device port (e.g. COM1, /dev/ttyACM0, etc.).

        Raises:
            IngeniaLinkCreationError: If the network cannot be created.
    """

    def __init__(self, port, timeout=100):
        net = lib.il_net_create(_cstr(port))
        _raise_null(net)

        self._net = ffi.gc(net, lib.il_net_destroy)

    @classmethod
    def _from_existing(cls, net):
        """ Create a new class instance from an existing network. """

        inst = cls.__new__(cls)
        inst._net = ffi.gc(net, lib.il_net_destroy)

        return inst

    @property
    def state(self):
        """ int: Obtain network state. """

        return lib.il_net_state_get(self._net)

    def servos(self, on_found=None):
        """ Obtain a list of attached servos.

            Args:
                on_found (callback, optional): Servo found callback.

            Returns:
                list: List of attached servos.
        """

        if on_found:
            self._on_found = on_found

            callback = lib._on_found_cb
            handle = ffi.new_handle(self)
        else:
            self._on_found = ffi.NULL

            callback = ffi.NULL
            handle = ffi.NULL

        servos = lib.il_net_servos_list_get(self._net, callback, handle)

        found = []
        curr = servos

        while curr:
            found.append(int(curr.id))
            curr = curr.next

        lib.il_net_servos_list_destroy(servos)

        return found


@ffi.def_extern()
def _on_evt_cb(ctx, evt, port):
    """ On event callback shim. """

    self = ffi.from_handle(ctx)
    evt_ = EVT_ADDED if evt == lib.IL_NET_DEV_EVT_ADDED else EVT_REMOVED

    self._on_evt(evt_, _pstr(port))


class NetworkMonitor(object):
    """ IngeniaLink network monitor.

        Raises:
            IngeniaLinkCreationError: If the monitor cannot be created.
    """

    def __init__(self):
        mon = lib.il_net_dev_mon_create()
        _raise_null(mon)

        self._mon = ffi.gc(mon, lib.il_net_dev_mon_destroy)

    def start(self, on_evt):
        """ Start the monitor.

            Args:
                on_evt (callback): Callback function.
        """

        self._on_evt = on_evt
        self._handle = ffi.new_handle(self)

        r = lib.il_net_dev_mon_start(self._mon, lib._on_evt_cb, self._handle)
        _raise_err(r)

    def stop(self):
        """ Stop the monitor. """

        lib.il_net_dev_mon_stop(self._mon)


@ffi.def_extern()
def _on_state_change_cb(ctx, state, flags):
    """ On state change callback shim. """

    cb = ffi.from_handle(ctx)
    cb(state, flags)


@ffi.def_extern()
def _on_emcy_cb(ctx, code):
    """ On emergency callback shim. """

    cb = ffi.from_handle(ctx)
    cb(code)


class Servo(object):
    """ IngeniaLink network servo.

        Args:
            net (Network): Network instance.
            id (int): Servo id.
            timeout (int, optional): Communications timeout (ms).

        Raises:
            IngeniaLinkCreationError: If the servo cannot be created.
    """

    def __init__(self, net, servo_id, timeout=100):
        servo = lib.il_servo_create(net._net, servo_id, timeout)
        _raise_null(servo)

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

    @property
    def state(self):
        """ tuple: Servo state and state flags. """

        state = ffi.new('il_servo_state_t *')
        flags = ffi.new('int *')

        lib.il_servo_state_get(self._servo, state, flags)

        return state[0], flags[0]

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
            _raise_err(slot)

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
            _raise_err(slot)

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
    def name(self):
        """ str: Name. """

        name = ffi.new('char []', lib.IL_SERVO_NAME_SZ)

        r = lib.il_servo_name_get(self._servo, name, ffi.sizeof(name))
        _raise_err(r)

        return _pstr(name)

    @name.setter
    def name(self, name):
        name_ = ffi.new('char []', _cstr(name))

        r = lib.il_servo_name_set(self._servo, name_)
        _raise_err(r)

    @property
    def info(self):
        """ dict: Servo information. """

        info = ffi.new('il_servo_info_t *')

        r = lib.il_servo_info_get(self._servo, info)
        _raise_err(r)

        return {'serial': info.serial,
                'name': _pstr(info.name),
                'sw_version': _pstr(info.sw_version),
                'hw_variant': _pstr(info.hw_variant),
                'prod_code': info.prod_code,
                'revision': info.revision}

    def store_all(self):
        """ Store all servo current parameters to the NVM. """

        r = lib.il_servo_store_all(self._servo)
        _raise_err(r)

    def store_comm(self):
        """ Store all servo current communications to the NVM. """

        r = lib.il_servo_store_comm(self._servo)
        _raise_err(r)

    def store_app(self):
        """ Store all servo current application parameters to the NVM. """

        r = lib.il_servo_store_app(self._servo)
        _raise_err(r)

    def raw_read(self, reg):
        """ Raw read from servo.

            Args:
                reg (Register): Register.

            Returns:
                int: Otained value

            Raises:
                TypeError: If the register type is not valid.
        """

        if not isinstance(reg, Register):
            raise TypeError('Invalid register type')

        # obtain data pointer and function to call
        t, f = _raw_read[reg.dtype]
        v = ffi.new(t)

        r = f(self._servo, reg._reg, v)
        _raise_err(r)

        return v[0]

    def read(self, reg):
        """ Read from servo.

            Args:
                reg (Register): Register.

            Returns:
                float: Otained value

            Raises:
                TypeError: If the register type is not valid.
        """

        if not isinstance(reg, Register):
            raise TypeError('Invalid register type')

        v = ffi.new('double *')
        r = lib.il_servo_read(self._servo, reg._reg, v)
        _raise_err(r)

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

        if not isinstance(reg, Register):
            raise TypeError('Invalid register type')

        # validate data (auto cast floats)
        if isinstance(data, float):
            data = int(data)
        elif not isinstance(data, int):
            raise TypeError('Unsupported data type')

        # obtain function to call
        f = _raw_write[reg.dtype]

        r = f(self._servo, reg._reg, data, confirm)
        _raise_err(r)

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

        if not isinstance(reg, Register):
            raise TypeError('Invalid register type')

        if not isinstance(data, (int, float)):
            raise TypeError('Unsupported data type')

        r = lib.il_servo_write(self._servo, reg._reg, data, confirm)
        _raise_err(r)

    def units_update(self):
        """ Update units scaling factors.

            Notes:
                This must be called if any encoder parameter, rated torque or
                pole pitch are changed, otherwise, the readings conversions
                will not be correct.
        """

        r = lib.il_servo_units_update(self._servo)
        _raise_err(r)

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
        """ int: Torque units. """
        return lib.il_servo_units_torque_get(self._servo)

    @units_torque.setter
    def units_torque(self, units):
        if units not in _UNITS_TORQUE_ALL:
            raise ValueError('Unsupported torque units')

        lib.il_servo_units_torque_set(self._servo, units)

    @property
    def units_pos(self):
        """ int: Position units. """
        return lib.il_servo_units_pos_get(self._servo)

    @units_pos.setter
    def units_pos(self, units):
        if units not in _UNITS_POS_ALL:
            raise ValueError('Unsupported position units')

        lib.il_servo_units_pos_set(self._servo, units)

    @property
    def units_vel(self):
        """ int: Velocity units. """
        return lib.il_servo_units_vel_get(self._servo)

    @units_vel.setter
    def units_vel(self, units):
        if units not in _UNITS_VEL_ALL:
            raise ValueError('Unsupported velocity units')

        lib.il_servo_units_vel_set(self._servo, units)

    @property
    def units_acc(self):
        """ int: Acceleration units. """
        return lib.il_servo_units_acc_get(self._servo)

    @units_acc.setter
    def units_acc(self, units):
        if units not in _UNITS_ACC_ALL:
            raise ValueError('Unsupported acceleration units')

        lib.il_servo_units_acc_set(self._servo, units)

    def disable(self):
        """ Disable PDS. """

        r = lib.il_servo_disable(self._servo)
        _raise_err(r)

    def switch_on(self, timeout=1000):
        """ Switch on PDS.

            This function switches on the PDS but it does not enable the motor.
            For most application cases, you should only use the `enable`
            function.

            Args:
                timeout (int, optional): Timeout (ms).
        """

        r = lib.il_servo_switch_on(self._servo, timeout)
        _raise_err(r)

    def enable(self, timeout=1000):
        """ Enable PDS.

            Args:
                timeout (int, optional): Timeout (ms).
        """

        r = lib.il_servo_enable(self._servo, timeout)
        _raise_err(r)

    def fault_reset(self):
        """ Fault reset. """

        r = lib.il_servo_fault_reset(self._servo)
        _raise_err(r)

    @property
    def mode(self):
        """ int: Operation mode. """

        mode = ffi.new('il_servo_mode_t *')

        r = lib.il_servo_mode_get(self._servo, mode)
        _raise_err(r)

        return mode[0]

    @mode.setter
    def mode(self, mode):
        if mode not in _MODE_ALL:
            raise ValueError('Unsupported mode')

        r = lib.il_servo_mode_set(self._servo, mode)
        _raise_err(r)

    def homing_start(self):
        """ Start the homing procedure. """

        r = lib.il_servo_homing_start(self._servo)
        _raise_err(r)

    def homing_wait(self, timeout):
        """ Wait until homing completes.

            Notes:
                The homing itself has a configurable timeout. The timeout given
                here is purely a 'communications' timeout, e.g. it could happen
                that the statusword change is never received. This timeout
                should be >= than the programmed homing timeout.

            Args:
                timeout (int): Timeout (ms).
        """

        r = lib.il_servo_homing_wait(self._servo, timeout)
        _raise_err(r)

    @property
    def ol_voltage(self):
        """ float: Open loop voltage (% relative to DC-bus, -1...1). """

        voltage = ffi.new('double *')
        r = lib.il_servo_ol_voltage_get(self._servo, voltage)
        _raise_err(r)

        return voltage[0]

    @ol_voltage.setter
    def ol_voltage(self, voltage):
        """ Set the open loop voltage (% relative to DC-bus, -1...1). """

        r = lib.il_servo_ol_voltage_set(self._servo, voltage)
        _raise_err(r)

    @property
    def ol_frequency(self):
        """ float: Open loop frequency (mHz). """

        frequency = ffi.new('double *')
        r = lib.il_servo_ol_frequency_get(self._servo, frequency)
        _raise_err(r)

        return frequency[0]

    @ol_frequency.setter
    def ol_frequency(self, frequency):
        """ Set the open loop frequency (mHz). """

        r = lib.il_servo_ol_frequency_set(self._servo, frequency)
        _raise_err(r)

    @property
    def torque(self):
        """ float: Actual torque. """

        torque = ffi.new('double *')
        r = lib.il_servo_torque_get(self._servo, torque)
        _raise_err(r)

        return torque[0]

    @torque.setter
    def torque(self, torque):
        """ Set the target torque. """

        r = lib.il_servo_torque_set(self._servo, torque)
        _raise_err(r)

    @property
    def position(self):
        """ float: Actual position. """

        position = ffi.new('double *')
        r = lib.il_servo_position_get(self._servo, position)
        _raise_err(r)

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
                    - sp_timeout (int): Set-point acknowledge timeout (ms).
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
                sp_timeout = int(pos[1]['sp_timeout'])

            pos = pos[0]

        r = lib.il_servo_position_set(self._servo, pos, immediate, relative,
                                      sp_timeout)
        _raise_err(r)

    @property
    def position_res(self):
        """ int: Position resolution (c/rev/s, c/ppitch/s). """

        res = ffi.new('uint32_t *')
        r = lib.il_servo_position_res_get(self._servo, res)
        _raise_err(r)

        return res[0]

    @property
    def velocity(self):
        """ float: Actual velocity. """

        velocity = ffi.new('double *')
        r = lib.il_servo_velocity_get(self._servo, velocity)
        _raise_err(r)

        return velocity[0]

    @velocity.setter
    def velocity(self, velocity):
        """ Set the target velocity. """

        r = lib.il_servo_velocity_set(self._servo, velocity)
        _raise_err(r)

    @property
    def velocity_res(self):
        """ int: Velocity resolution (c/rev, c/ppitch). """

        res = ffi.new('uint32_t *')
        r = lib.il_servo_velocity_res_get(self._servo, res)
        _raise_err(r)

        return res[0]

    def wait_reached(self, timeout):
        """ Wait until the servo does a target reach.

            Args:
                timeout (float): Timeout (ms).
        """

        r = lib.il_servo_wait_reached(self._servo, timeout)
        _raise_err(r)


class Poller(object):
    """ Register poller.

        Args:
            servo (Servo): Servo.
            n_ch (int): Number of channels.

        Raises:
            IngeniaLinkCreationError: If the poller cannot be created.
    """

    def __init__(self, servo, n_ch):
        poller = lib.il_poller_create(servo._servo, n_ch)
        _raise_null(poller)

        self._poller = ffi.gc(poller, lib.il_poller_destroy)

        self._n_ch = n_ch
        self._acq = ffi.new('il_poller_acq_t **')

    def start(self):
        """ Start poller. """

        r = lib.il_poller_start(self._poller)
        _raise_err(r)

    def stop(self):
        """ Stop poller. """

        lib.il_poller_stop(self._poller)

    @property
    def data(self):
        """ tuple (list, list, bool): Time vector, array of data vectors and a
            flag indicating if data was lost.
        """

        lib.il_poller_data_get(self._poller, self._acq)
        acq = ffi.cast('il_poller_acq_t *', self._acq[0])

        t = list(acq.t[0:acq.cnt])

        d = []
        for ch in range(self._n_ch):
            if acq.d[ch] != ffi.NULL:
                d.append(list(acq.d[ch][0:acq.cnt]))
            else:
                d.append(None)

        return t, d, bool(acq.lost)

    def configure(self, t_s, sz):
        """ Configure.

            Args:
                t_s (int): Polling period (ms).
                sz (int): Buffer size.
        """

        r = lib.il_poller_configure(self._poller, t_s, sz)
        _raise_err(r)

    def ch_configure(self, ch, reg):
        """ Configure a poller channel mapping.

            Args:
                ch (int): Channel to be configured.
                reg (Register): Register to associate to the given channel.

            Raises:
                TypeError: If the register is not valid.
        """

        if not isinstance(reg, Register):
            raise TypeError('Invalid register')

        r = lib.il_poller_ch_configure(self._poller, ch, reg._reg)
        _raise_err(r)

    def ch_disable(self, ch):
        """ Disable a channel.

            Args:
                ch (int): Channel to be disabled.
        """

        r = lib.il_poller_ch_disable(self._poller, ch)
        _raise_err(r)

    def ch_disable_all(self):
        """ Disable all channels. """

        r = lib.il_poller_ch_disable_all(self._poller)
        _raise_err(r)


class Monitor(object):
    """ Monitor.

        Args:
            servo (Servo): Servo instance.
    """

    def __init__(self, servo):
        monitor = lib.il_monitor_create(servo._servo)
        _raise_null(monitor)

        self._monitor = ffi.gc(monitor, lib.il_monitor_destroy)

        self._acq = ffi.new('il_monitor_acq_t **')

    def start(self):
        """ Start the monitor. """

        r = lib.il_monitor_start(self._monitor)
        _raise_err(r)

    def stop(self):
        """ Stop the monitor. """

        r = lib.il_monitor_stop(self._monitor)
        _raise_err(r)

    def wait(self, timeout):
        """ Wait until the current acquisition finishes.

            Args:
                timeout (int): Timeout (ms).
        """

        r = lib.il_monitor_wait(self._monitor, timeout)
        _raise_err(r)

    @property
    def data(self):
        """ tuple: Current acquisition time and data for all channels. """

        lib.il_monitor_data_get(self._monitor, self._acq)
        acq = ffi.cast('il_monitor_acq_t *', self._acq[0])

        t = list(acq.t[0:acq.cnt])

        d = []
        for ch in range(lib.IL_MONITOR_CH_NUM):
            if acq.d[ch] != ffi.NULL:
                d.append(list(acq.d[ch][0:acq.cnt]))
            else:
                d.append(None)

        return t, d

    def configure(self, t_s, delay_samples=0, max_samples=0):
        """ Configure the monitor parameters.

            Args:
                t_s (int, float): Sampling period (resolution: 100 us).
                delay_samples (int, optional): Delay samples.
                max_samples (int, optional): Maximum acquisition samples.
        """

        r = lib.il_monitor_configure(self._monitor, t_s, delay_samples,
                                     max_samples)
        _raise_err(r)

    def ch_configure(self, ch, reg):
        """ Configure a channel mapping.

            Args:
                ch (int): Channel.
                reg (Register): Register to be mapped to the given channel.
        """

        if not isinstance(reg, Register):
            raise TypeError('Invalid register')

        r = lib.il_monitor_ch_configure(self._monitor, ch, reg._reg)
        _raise_err(r)

    def ch_disable(self, ch):
        """ Disable a channel. """

        r = lib.il_monitor_ch_disable(self._monitor, ch)
        _raise_err(r)

    def ch_disable_all(self):
        """ Disable all channels. """

        r = lib.il_monitor_ch_disable_all(self._monitor)
        _raise_err(r)

    def trigger_configure(self, mode, delay_samples=0, source=None, th_pos=0.,
                          th_neg=0., din_msk=0):
        """ Configure the trigger.

            Args:
                mode (int): Trigger mode.
                delay_samples (int, optional): Delay samples.
                source (Register, optional): Source register, required for
                    MONITOR_TRIGGER_POS, MONITOR_TRIGGER_NEG and
                    MONITOR_TRIGGER_WINDOW.
                th_pos (int, float, optional): Positive threshold, used for
                    MONITOR_TRIGGER_POS, MONITOR_TRIGGER_WINDOW
                th_neg (int, float, optional): Negative threshold, used for
                    MONITOR_TRIGGER_NEG, MONITOR_TRIGGER_WINDOW
                din_msk (int, optional): Digital input mask, used for
                    MONITOR_TRIGGER_DIN
        """

        _source_required = (MONITOR_TRIGGER_POS, MONITOR_TRIGGER_NEG,
                            MONITOR_TRIGGER_WINDOW)

        if mode not in _MONITOR_TRIGGER_ALL:
            raise ValueError('Invalid trigger mode')

        if mode in _source_required:
            if not isinstance(source, Register):
                raise ValueError('Register required for the selected mode')

            reg = source._reg
        else:
            reg = ffi.NULL

        r = lib.il_monitor_trigger_configure(
                self._monitor, mode, delay_samples, reg, th_pos, th_neg,
                din_msk)
        _raise_err(r)
