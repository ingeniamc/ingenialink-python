from enum import Enum

from ._ingenialink import lib, ffi
from ._utils import cstr, pstr, raise_null, raise_err


class NET_STATE(Enum):
    """ Network State. """

    OPERATIVE = lib.IL_NET_STATE_OPERATIVE
    """ Operative. """
    FAULTY = lib.IL_NET_STATE_FAULTY
    """ Faulty. """


class NET_DEV_EVT:
    """ Device Event. """

    ADDED = lib.IL_NET_DEV_EVT_ADDED
    """ Added. """
    REMOVED = lib.IL_NET_DEV_EVT_REMOVED
    """ Event. """


def devices():
    """ Obtain a list of network devices.

        Returns:
            list: List of network devices.
    """

    devs = lib.il_net_dev_list_get()

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
            port (str): Network device port (e.g. COM1, /dev/ttyACM0, etc.).

        Raises:
            ILCreationError: If the network cannot be created.
    """

    def __init__(self, port):
        net = lib.il_net_create(cstr(port))
        raise_null(net)

        self._net = ffi.gc(net, lib.il_net_destroy)

    @classmethod
    def _from_existing(cls, net):
        """ Create a new class instance from an existing network. """

        inst = cls.__new__(cls)
        inst._net = ffi.gc(net, lib.il_net_destroy)

        return inst

    @property
    def state(self):
        """ NET_STATE: Obtain network state. """

        return NET_STATE(lib.il_net_state_get(self._net))

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

        Raises:
            ILCreationError: If the monitor cannot be created.
    """

    def __init__(self):
        mon = lib.il_net_dev_mon_create()
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
