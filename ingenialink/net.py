from enum import Enum

from ._ingenialink import lib, ffi
from ._utils import cstr, pstr, raise_null, raise_err, to_ms


class NET_PROT(Enum):
    """ Network Protocol. """

    EUSB = lib.IL_NET_PROT_EUSB
    """ E-USB. """
    MCB = lib.IL_NET_PROT_MCB
    """ MCB. """


class NET_STATE(Enum):
    """ Network State. """

    CONNECTED = lib.IL_NET_STATE_CONNECTED
    """ Connected. """
    DISCONNECTED = lib.IL_NET_STATE_DISCONNECTED
    """ Disconnected. """
    FAULTY = lib.IL_NET_STATE_FAULTY
    """ Faulty. """


class NET_DEV_EVT(Enum):
    """ Device Event. """

    ADDED = lib.IL_NET_DEV_EVT_ADDED
    """ Added. """
    REMOVED = lib.IL_NET_DEV_EVT_REMOVED
    """ Event. """


def devices(prot):
    """ Obtain a list of network devices.

        Args:
            prot (NET_PROT): Protocol.

        Returns:
            list: List of network devices.

        Raises:
            TypeError: If the protocol type is invalid.
    """

    if not isinstance(prot, NET_PROT):
        raise TypeError('Invalid protocol')

    devs = lib.il_net_dev_list_get(prot.value)

    found = []
    curr = devs

    while curr:
        found.append(pstr(curr.port))
        curr = curr.next

    lib.il_net_dev_list_destroy(devs)

    return found


@ffi.def_extern()
def _on_found_cb(ctx, servo_id):
    """ On found callback shim. """

    self = ffi.from_handle(ctx)
    self._on_found(int(servo_id))


class Network(object):
    """ Network.

        Args:
            prot (NET_PROT): Protocol.
            port (str): Network device port (e.g. COM1, /dev/ttyACM0, etc.).
            timeout_rd (int, float, optional): Read timeout (s).
            timeout_wr (int, float, optional): Write timeout (s).

        Raises:
            TypeError: If the protocol type is invalid.
            ILCreationError: If the network cannot be created.
    """

    def __init__(self, prot, port, timeout_rd=0.5, timeout_wr=0.5):
        if not isinstance(prot, NET_PROT):
            raise TypeError('Invalid protocol')

        port_ = ffi.new('char []', cstr(port))
        opts = ffi.new('il_net_opts_t *')

        opts.port = port_
        opts.timeout_rd = to_ms(timeout_rd)
        opts.timeout_wr = to_ms(timeout_wr)

        net = lib.il_net_create(prot.value, opts)
        raise_null(net)

        self._net = ffi.gc(net, lib.il_net_destroy)

    @classmethod
    def _from_existing(cls, net):
        """ Create a new class instance from an existing network. """

        inst = cls.__new__(cls)
        inst._net = ffi.gc(net, lib.il_net_destroy)

        return inst

    @property
    def prot(self):
        """ NET_PROT: Obtain network protocol. """

        return NET_PROT(lib.il_net_prot_get(self._net))

    @property
    def state(self):
        """ NET_STATE: Obtain network state. """

        return NET_STATE(lib.il_net_state_get(self._net))

    @property
    def port(self):
        """ str: Obtain network port. """

        port = lib.il_net_port_get(self._net)
        return pstr(port)

    def connect(self):
        """ Connect network. """

        r = lib.il_net_connect(self._net)
        raise_err(r)

    def disconnect(self):
        """ Disconnect network. """

        lib.il_net_disconnect(self._net)

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
    self._on_evt(NET_DEV_EVT(evt), pstr(port))


class NetworkMonitor(object):
    """ Network Monitor.

        Args:
            prot (NET_PROT): Protocol.

        Raises:
            TypeError: If the protocol type is invalid.
            ILCreationError: If the monitor cannot be created.
    """

    def __init__(self, prot):
        if not isinstance(prot, NET_PROT):
            raise TypeError('Invalid protocol')

        mon = lib.il_net_dev_mon_create(prot.value)
        raise_null(mon)

        self._mon = ffi.gc(mon, lib.il_net_dev_mon_destroy)

    def start(self, on_evt):
        """ Start the monitor.

            Args:
                on_evt (callback): Callback function.
        """

        self._on_evt = on_evt
        self._handle = ffi.new_handle(self)

        r = lib.il_net_dev_mon_start(self._mon, lib._on_evt_cb, self._handle)
        raise_err(r)

    def stop(self):
        """ Stop the monitor. """

        lib.il_net_dev_mon_stop(self._mon)
