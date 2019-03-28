from enum import Enum
from time import sleep

from ._ingenialink import lib, ffi
from ._utils import cstr, pstr, raise_null, raise_err, to_ms
import numpy as np
from .registers import REG_DTYPE


class NET_PROT(Enum):
    """ Network Protocol. """

    EUSB = lib.IL_NET_PROT_EUSB
    """ E-USB. """
    MCB = lib.IL_NET_PROT_MCB
    """ MCB. """
    ETH = lib.IL_NET_PROT_ETH
    """ ETH. """
    VIRTUAL = lib.IL_NET_PROT_VIRTUAL
    """ VIRTUAL. """


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

        self._net = lib.il_net_create(prot.value, opts)

        raise_null(self._net)
        # self._net = ffi.gc(self._net, lib.il_net_destroy)


    @classmethod
    def _from_existing(cls, net):
        """ Create a new class instance from an existing network. """

        inst = cls.__new__(cls)
        inst._net = ffi.gc(net, lib.il_net_destroy)

        return inst

    def monitoring_channel_data(self, channel, dtype):
        data_arr = []
        size = int(self.monitoring_data_size)
        bytes_per_block = self.monitoring_get_bytes_per_block()
        if dtype == REG_DTYPE.U16:
            data_arr = lib.il_net_monitoring_channel_u16(self._net, channel)
        elif dtype == REG_DTYPE.S16:
            data_arr = lib.il_net_monitoring_channel_s16(self._net, channel)
        elif dtype == REG_DTYPE.U32:
            data_arr = lib.il_net_monitoring_channel_u32(self._net, channel)
        elif dtype == REG_DTYPE.S32:
            data_arr = lib.il_net_monitoring_channel_s32(self._net, channel)
        elif dtype == REG_DTYPE.FLOAT:
            data_arr = lib.il_net_monitoring_channel_flt(self._net, channel)
        ret_arr = []
        for i in range(0, int(size / bytes_per_block)):
            ret_arr.append(data_arr[i])
        return ret_arr

    def monitoring_remove_all_mapped_registers(self):
        return lib.il_net_remove_all_mapped_registers(self._net)

    def monitoring_set_mapped_register(self, channel, reg_idx, dtype):
        return lib.il_net_set_mapped_register(self._net, channel, reg_idx, dtype)

    def monitoring_get_num_mapped_registers(self):
        return lib.il_net_num_mapped_registers_get(self._net)

    def monitoring_enable(self):
        return lib.il_net_enable_monitoring(self._net)

    def monitoring_disable(self):
        return lib.il_net_disable_monitoring(self._net)

    def monitoring_read_data(self):
        return lib.il_net_read_monitoring_data(self._net)

    def monitoring_get_bytes_per_block(self):
        return lib.il_net_monitornig_bytes_per_block_get(self._net)

    # Disturbance
    def disturbance_channel_data(self, channel, dtype, data_arr):
        if dtype == REG_DTYPE.U16:
            lib.il_net_disturbance_data_u16_set(self._net, channel, data_arr)
        elif dtype == REG_DTYPE.S16:
            lib.il_net_disturbance_data_s16_set(self._net, channel, data_arr)
        elif dtype == REG_DTYPE.U32:
            lib.il_net_disturbance_data_u32_set(self._net, channel, data_arr)
        elif dtype == REG_DTYPE.S32:
            lib.il_net_disturbance_data_s32_set(self._net, channel, data_arr)
        elif dtype == REG_DTYPE.FLOAT:
            lib.il_net_disturbance_data_flt_set(self._net, channel, data_arr)
        return 0

    def disturbance_remove_all_mapped_registers(self):
        return lib.il_net_disturbance_remove_all_mapped_registers(self._net)

    def disturbance_set_mapped_register(self, channel, address, dtype):
        return lib.il_net_disturbance_set_mapped_register(self._net, channel, address, dtype);

    # Properties
    @property
    def prot(self):
        """ NET_PROT: Obtain network protocol. """

        return NET_PROT(lib.il_net_prot_get(self._net))

    @property
    def state(self):
        """ NET_STATE: Obtain network state. """

        return NET_STATE(lib.il_net_state_get(self._net))

    @property
    def status(self):
        """ NET_STATUS: Obtain network status. """

        return lib.il_net_status_get(self._net)

    @property
    def port(self):
        """ str: Obtain network port. """

        port = lib.il_net_port_get(self._net)
        return pstr(port)

    @property
    def extended_buffer(self):
        """" str: Obtain extended buffer. """
        ext_buff = lib.il_net_extended_buffer_get(self._net)
        return pstr(ext_buff)


    @property
    def monitoring_data(self):
        """ arr: Obtain monitoring data. """
        monitoring_data = lib.il_net_monitornig_data_get(self._net)
        size = int(self.monitoring_data_size / 2)
        ret_arr = []
        for i in range(0, size):
            ret_arr.append(monitoring_data[i])
        return ret_arr

    @property
    def monitoring_data_size(self):
        """ int: Obtain monitoring data size """
        return lib.il_net_monitornig_data_size_get(self._net)

    @property
    def disturbance_data(self):
        disturbance_data = lib.il_net_disturbance_data_get(self._net)
        size = int(self.disturbance_data_size / 2)
        ret_arr = []
        for i in range(0, size):
            ret_arr.append(disturbance_data[i])
        return ret_arr

    @disturbance_data.setter
    def disturbance_data(self, value):
        disturbance_arr = value
        disturbance_arr = np.pad(disturbance_arr, (0, int(self.disturbance_data_size / 2) - len(value)), 'constant')
        lib.il_net_disturbance_data_set(self._net, disturbance_arr.tolist())

    @property
    def disturbance_data_size(self):
        return lib.il_net_disturbance_data_size_get(self._net)

    @disturbance_data_size.setter
    def disturbance_data_size(self, value):
        lib.il_net_disturbance_data_size_set(self._net, value)

    def close_socket(self):
        return lib.il_net_close_socket(self._net)

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

    def net_mon_status(self, on_evt):
        if self.prot == NET_PROT.ETH:
            status = self.status
            while True:
                if status != self.status:
                    if self.status == 0:
                        on_evt(NET_DEV_EVT.ADDED)
                    elif self.status == 1:
                        on_evt(NET_DEV_EVT.REMOVED)
                    status = self.status
                sleep(1)

    def net_mon_stop(self):
        lib.il_net_mon_stop(self._net)

    def destroy_network(self):
        lib.il_net_destroy(self._net)

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
