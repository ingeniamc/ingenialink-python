from ._ingenialink import ffi, lib
from ._utils import _cstr, _pstr
from . import exceptions as exc


__version__ = '1.1.2'


U8 = 1
""" int: Unsigned 8-bit integer type. """
S8 = 2
""" int: Signed 8-bit integer type. """
U16 = 3
""" int: Unsigned 16-bit integer type. """
S16 = 4
""" int: Signed 16-bit integer type. """
U32 = 5
""" int: Unsigned 32-bit integer type. """
S32 = 6
""" int: Signed 32-bit integer type. """
U64 = 7
""" int: Unsigned 64-bit integer type. """
S64 = 8
""" int: Signed 64-bit integer type. """

EVT_ADDED = 0
""" int: Device added event. """
EVT_REMOVED = 1
""" int: Device removed event. """

_read = {U8: ['uint8_t *', lib.il_node_read_u8],
         S8: ['int8_t *', lib.il_node_read_s8],
         U16: ['uint16_t *', lib.il_node_read_u16],
         S16: ['int16_t *', lib.il_node_read_s16],
         U32: ['uint32_t *', lib.il_node_read_u32],
         S32: ['int32_t *', lib.il_node_read_s32],
         U64: ['uint64_t *', lib.il_node_read_u64],
         S64: ['int64_t *', lib.il_node_read_s64]}
""" dict: Data buffer and function mappings for read operation. """

_write = {U8: lib.il_node_write_u8,
          S8: lib.il_node_write_s8,
          U16: lib.il_node_write_u16,
          S16: lib.il_node_write_s16,
          U32: lib.il_node_write_u32,
          S32: lib.il_node_write_s32,
          U64: lib.il_node_write_u64,
          S64: lib.il_node_write_s64}
""" dict: Function mappings for write operation. """


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
    else:
        raise exc.IngeniaLinkError(msg)


class Register(object):
    """ IngeniaLink node register.

        Notes:
            The supported data types are SX/UX (X = 8, 16, 32, 64), all defined
            in the ``ingenialink`` package.

        Args:
            idx (int): Reigtser index.
            sidx (int): Register subindex.
            dtype (int): Register data type.

        Raises:
            ValueError: If the data type is unsupported.
    """

    def __init__(self, idx, sidx, dtype):
        if dtype not in (U8, S8, U16, S16, U32, S32, U64, S64):
            raise ValueError('Unsupported register data type')

        self._idx = idx
        self._sidx = sidx
        self._dtype = dtype

    @property
    def idx(self):
        """ int: Register index. """
        return self._idx

    @property
    def sidx(self):
        """ int: Register subindex. """
        return self._sidx

    @property
    def dtype(self):
        """ int: Register data type. """
        return self._dtype


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
def _on_found_cb(ctx, node_id):
    """ On found callback shim. """

    self = ffi.from_handle(ctx)
    self._on_found(int(node_id))


class Network(object):
    """ IngeniaLink network.

        Args:
            port (str): Network device port (e.g. COM1, /dev/ttyACM0, etc.).
            timeout (int, optional): Communications timeout (ms).

        Raises:
            IngeniaLinkCreationError: If the network cannot be created.
    """

    def __init__(self, port, timeout=100):
        self._net = lib.il_net_create(_cstr(port), timeout)
        _raise_null(self._net)

    def __del__(self):
        lib.il_net_destroy(self._net)

    def nodes(self, on_found=None):
        """ Obtain a list of attached nodes.

            Args:
                on_found (callback, optional): Node found callback.

            Returns:
                list: List of attached nodes.
        """

        if on_found:
            self._on_found = on_found

            callback = lib._on_found_cb
            handle = ffi.new_handle(self)
        else:
            self._on_found = ffi.NULL

            callback = ffi.NULL
            handle = ffi.NULL

        nodes = lib.il_net_nodes_list_get(self._net, callback, handle)

        found = []
        curr = nodes

        while curr:
            found.append(int(curr.id))
            curr = curr.next

        lib.il_net_nodes_list_destroy(nodes)

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


class Node(object):
    """ IngeniaLink network node.

        Args:
            net (Network): Network instance.
            id (int): Node id.

        Raises:
            IngeniaLinkCreationError: If the node cannot be created.
    """

    def __init__(self, net, node_id):
        # keep network reference
        self._net = net

        self._node = lib.il_node_create(self._net._net, node_id)
        _raise_null(self._node)

    def __del__(self):
        lib.il_node_destroy(self._node)

    def read(self, reg):
        """ Read from node.

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
        t, f = _read[reg.dtype]
        v = ffi.new(t)

        r = f(self._node, reg.idx, reg.sidx, v)
        _raise_err(r)

        return v[0]

    def write(self, reg, data):
        """ Write to node.

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
        f = _write[reg.dtype]

        r = f(self._node, reg.idx, reg.sidx, data)
        _raise_err(r)
