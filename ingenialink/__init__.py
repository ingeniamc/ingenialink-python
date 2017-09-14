import warnings

from ._ingenialink import ffi, lib
from ._utils import _cstr, _pstr
from . import exceptions as exc


__version__ = '1.9.9'


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

_PHY_ALL = (PHY_NONE, PHY_TORQUE, PHY_POS, PHY_VEL, PHY_ACC)
""" tuple: All physical units. """

MODE_PP = lib.IL_AXIS_MODE_PP
""" int: Profile position mode. """
MODE_PV = lib.IL_AXIS_MODE_PV
""" int: Profile velocity mode. """
MODE_PT = lib.IL_AXIS_MODE_PT
""" int: Profile torque mode. """
MODE_HOMING = lib.IL_AXIS_MODE_HOMING
""" int: Homing mode. """

_MODE_ALL = (MODE_PP, MODE_PV, MODE_PT, MODE_HOMING)
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

EVT_ADDED = 0
""" int: Device added event. """
EVT_REMOVED = 1
""" int: Device removed event. """

_raw_read = {DTYPE_U8: ['uint8_t *', lib.il_axis_raw_read_u8],
             DTYPE_S8: ['int8_t *', lib.il_axis_raw_read_s8],
             DTYPE_U16: ['uint16_t *', lib.il_axis_raw_read_u16],
             DTYPE_S16: ['int16_t *', lib.il_axis_raw_read_s16],
             DTYPE_U32: ['uint32_t *', lib.il_axis_raw_read_u32],
             DTYPE_S32: ['int32_t *', lib.il_axis_raw_read_s32],
             DTYPE_U64: ['uint64_t *', lib.il_axis_raw_read_u64],
             DTYPE_S64: ['int64_t *', lib.il_axis_raw_read_s64]}
""" dict: Data buffer and function mappings for raw read operation. """

_raw_write = {DTYPE_U8: lib.il_axis_raw_write_u8,
              DTYPE_S8: lib.il_axis_raw_write_s8,
              DTYPE_U16: lib.il_axis_raw_write_u16,
              DTYPE_S16: lib.il_axis_raw_write_s16,
              DTYPE_U32: lib.il_axis_raw_write_u32,
              DTYPE_S32: lib.il_axis_raw_write_s32,
              DTYPE_U64: lib.il_axis_raw_write_u64,
              DTYPE_S64: lib.il_axis_raw_write_s64}
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
    elif code == lib.IL_EFAULT:
        raise exc.IngeniaLinkFaultError(msg)
    elif code == lib.IL_EDISCONN:
        raise exc.IngeniaLinkDisconnectionError(msg)
    elif code == lib.IL_EACCESS:
        raise exc.IngeniaLinkAccessError(msg)
    elif code == lib.IL_ESTATE:
        raise exc.IngeniaLinkStateError(msg)
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


@ffi.def_extern()
def _on_found_cb(ctx, axis_id):
    """ On found callback shim. """

    self = ffi.from_handle(ctx)
    self._on_found(int(axis_id))


class Network(object):
    """ IngeniaLink network.

        Args:
            port (str): Network device port (e.g. COM1, /dev/ttyACM0, etc.).

        Raises:
            IngeniaLinkCreationError: If the network cannot be created.
    """

    _net = None

    def __init__(self, port, timeout=100):
        self._net = lib.il_net_create(_cstr(port))
        _raise_null(self._net)

    def __del__(self):
        if self._net:
            lib.il_net_destroy(self._net)

    def axes(self, on_found=None):
        """ Obtain a list of attached axes.

            Args:
                on_found (callback, optional): Axis found callback.

            Returns:
                list: List of attached axes.
        """

        if on_found:
            self._on_found = on_found

            callback = lib._on_found_cb
            handle = ffi.new_handle(self)
        else:
            self._on_found = ffi.NULL

            callback = ffi.NULL
            handle = ffi.NULL

        axes = lib.il_net_axes_list_get(self._net, callback, handle)

        found = []
        curr = axes

        while curr:
            found.append(int(curr.id))
            curr = curr.next

        lib.il_net_axes_list_destroy(axes)

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
        self._mon = lib.il_net_dev_mon_create()
        _raise_null(self._mon)

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

    def __del__(self):
        lib.il_net_dev_mon_destroy(self._mon)


class Axis(object):
    """ IngeniaLink network axis.

        Args:
            net (Network): Network instance.
            id (int): Axis id.
            timeout (int, optional): Communications timeout (ms).

        Raises:
            IngeniaLinkCreationError: If the axis cannot be created.
    """

    _axis = None

    def __init__(self, net, axis_id, timeout=1000):
        # keep network reference
        self._net = net

        self._axis = lib.il_axis_create(self._net._net, axis_id, timeout)
        _raise_null(self._axis)

    def __del__(self):
        if self._axis:
            lib.il_axis_destroy(self._axis)

    def raw_read(self, reg):
        """ Raw read from axis.

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

        r = f(self._axis, reg._reg, v)
        _raise_err(r)

        return v[0]

    def read(self, reg):
        """ Read from axis.

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
        r = lib.il_axis_read(self._axis, reg._reg, v)
        _raise_err(r)

        return v[0]

    def raw_write(self, reg, data):
        """ Raw write to axis.

            Args:
                reg (Register): Register.
                data (int): Data.

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

        r = f(self._axis, reg._reg, data)
        _raise_err(r)

    def write(self, reg, data):
        """ Write to axis.

            Args:
                reg (Register): Register.
                data (int): Data.

            Raises:
                TypeError: If any of the arguments type is not valid or
                    unsupported.
        """

        if not isinstance(reg, Register):
            raise TypeError('Invalid register type')

        if not isinstance(data, (int, float)):
            raise TypeError('Unsupported data type')

        r = lib.il_axis_write(self._axis, reg._reg, data)
        _raise_err(r)

    @property
    def units_torque(self):
        """ int: Torque units. """
        return lib.il_axis_units_torque_get(self._axis)

    @units_torque.setter
    def units_torque(self, units):
        if units not in _UNITS_TORQUE_ALL:
            raise ValueError('Unsupported torque units')

        lib.il_axis_units_torque_set(self._axis, units)

    @property
    def units_pos(self):
        """ int: Position units. """
        return lib.il_axis_units_pos_get(self._axis)

    @units_pos.setter
    def units_pos(self, units):
        if units not in _UNITS_POS_ALL:
            raise ValueError('Unsupported position units')

        lib.il_axis_units_pos_set(self._axis, units)

    @property
    def units_vel(self):
        """ int: Velocity units. """
        return lib.il_axis_units_vel_get(self._axis)

    @units_vel.setter
    def units_vel(self, units):
        if units not in _UNITS_VEL_ALL:
            raise ValueError('Unsupported velocity units')

        lib.il_axis_units_vel_set(self._axis, units)

    @property
    def units_acc(self):
        """ int: Acceleration units. """
        return lib.il_axis_units_acc_get(self._axis)

    @units_acc.setter
    def units_acc(self, units):
        if units not in _UNITS_ACC_ALL:
            raise ValueError('Unsupported acceleration units')

        lib.il_axis_units_acc_set(self._axis, units)

    def enable(self):
        """ Enable PDS. """

        r = lib.il_axis_enable(self._axis)
        _raise_err(r)

    def disable(self):
        """ Disable PDS. """

        r = lib.il_axis_disable(self._axis)
        _raise_err(r)

    def fault_reset(self):
        """ Fault reset. """

        r = lib.il_axis_fault_reset(self._axis)
        _raise_err(r)

    @property
    def mode(self):
        """ int: Operation mode. """
        pass

    @mode.setter
    def mode(self, mode):
        if mode not in _MODE_ALL:
            raise ValueError('Unsupported mode')

        r = lib.il_axis_mode_set(self._axis, mode)
        _raise_err(r)

    def homing_start(self):
        """ Start the homing procedure. """

        r = lib.il_axis_homing_start(self._axis)
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

        r = lib.il_axis_homing_wait(self._axis, timeout)
        _raise_err(r)

    @property
    def torque(self):
        """ float: Actual torque. """

        torque = ffi.new('double *')
        r = lib.il_axis_torque_get(self._axis, torque)
        _raise_err(r)

        return torque[0]

    @torque.setter
    def torque(self, torque):
        """ Set the target torque. """

        r = lib.il_axis_torque_set(self._axis, torque)
        _raise_err(r)

    @property
    def position(self):
        """ float: Actual position. """

        position = ffi.new('double *')
        r = lib.il_axis_position_get(self._axis, position)
        _raise_err(r)

        return position[0]

    @position.setter
    def position(self, pos):
        """ Set the target position.

            Notes:
                Position can be either a single position, or a tuple/list
                containing in the first position the position, and in the
                second a dictionary with the following options:

                    - immediate (bool): If True, the axis will go to the
                      position immediately, otherwise it will push the position
                      to the buffer. Defaults to True.
                    - relative (bool): If True, the position will be taken as
                      relative, otherwise it will be taken as absolute.
                      Defaults to False.
        """

        immediate = 1
        relative = 0

        if isinstance(pos, (tuple, list)):
            if len(pos) != 2 or not isinstance(pos[1], dict):
                raise TypeError('Unexpected position')

            if 'immediate' in pos[1]:
                immediate = int(pos[1]['immediate'])

            if 'relative' in pos[1]:
                relative = int(pos[1]['relative'])

            pos = pos[0]

        r = lib.il_axis_position_set(self._axis, pos, immediate, relative)
        _raise_err(r)

    @property
    def velocity(self):
        """ float: Actual velocity. """

        velocity = ffi.new('double *')
        r = lib.il_axis_velocity_get(self._axis, velocity)
        _raise_err(r)

        return velocity[0]

    @velocity.setter
    def velocity(self, velocity):
        """ Set the target velocity. """

        r = lib.il_axis_velocity_set(self._axis, velocity)
        _raise_err(r)

    def wait_reached(self, timeout):
        """ Wait until the axis does a target reach.

            Args:
                timeout (float): Timeout (ms).
        """

        r = lib.il_axis_wait_reached(self._axis, timeout)
        _raise_err(r)


class Poller(object):
    """ Register poller.

        Args:
            axis (Axis): Axis.
            reg (Register): Register to be polled.
            period (int): Polling period (ms).
            sz (int): Buffer size.

        Raises:
            IngeniaLinkCreationError: If the poller cannot be created.
    """

    _poller = None

    def __init__(self, axis, reg, period, sz):
        self._axis = axis

        self._poller = lib.il_poller_create(axis._axis, reg._reg, period, sz)
        _raise_null(self._poller)

        self._t = ffi.new('double **')
        self._d = ffi.new('double **')
        self._cnt = ffi.new('size_t *')
        self._lost = ffi.new('int *')

    def __del__(self):
        if self._poller:
            lib.il_poller_destroy(self._poller)

    def start(self):
        """ Start poller. """

        r = lib.il_poller_start(self._poller)
        _raise_err(r)

    def stop(self):
        """ Stop poller. """

        lib.il_poller_stop(self._poller)

    @property
    def data(self):
        """ tuple (list, list): Current time and data vectors. """

        r = lib.il_poller_data_get(self._poller, self._t, self._d, self._cnt,
                                   self._lost)
        _raise_err(r)

        if self._lost[0]:
            warnings.warn('Data was lost (increase buffer or empty faster)')

        t = ffi.cast('double *', self._t[0])
        d = ffi.cast('double *', self._d[0])
        cnt = self._cnt[0]

        return list(t[0:cnt]), list(d[0:cnt])
