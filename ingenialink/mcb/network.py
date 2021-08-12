from ..network import Network, NET_PROT
from .._ingenialink import lib, ffi
from ingenialink.utils._utils import pstr, cstr, raise_null, raise_err

from ..utils._utils import to_ms


class MCBNetwork(Network):
    def __init__(self, timeout_rd=0.5, timeout_wr=0.5):
        self.__timeout_rd = timeout_rd
        self.__timeout_wr = timeout_wr

        self.__net_interface = None

    def load_firmware(self, fw_file):
        # TODO: Implement FTP fw loader
        raise NotImplementedError

    def scan_slaves(self):
        ports_found = self.devices()
        return ports_found

    def connect_to_slave(self, port=None):
        self._on_found = ffi.NULL

        callback = ffi.NULL
        handle = ffi.NULL

        opts = ffi.new('il_net_opts_t *')
        _port = ffi.new('char []', cstr(port))
        opts.port = _port
        opts.timeout_rd = to_ms(self.__timeout_rd)
        opts.timeout_wr = to_ms(self.__timeout_wr)

        self.__net_interface = lib.il_net_create(NET_PROT.MCB.value, opts)
        raise_null(self.__net_interface)

        servos = lib.il_net_servos_list_get(self.__net_interface, callback, handle)

        found = []
        curr = servos

        while curr:
            found.append(int(curr.id))
            curr = curr.next

        lib.il_net_servos_list_destroy(servos)

        return found

    def devices(self):
        """ Obtain a list of network devices.

        Returns:
            list: List of network devices.

        Raises:
            TypeError: If the protocol type is invalid.
        """
        devs = lib.il_net_dev_list_get(NET_PROT.MCB.value)

        found = []
        curr = devs

        while curr:
            found.append(pstr(curr.port))
            curr = curr.next

        lib.il_net_dev_list_destroy(devs)

        return found

    def disconnect_from_slave(self):
        raise NotImplementedError

    def restore_parameters(self):
        raise NotImplementedError

    def store_parameters(self):
        raise NotImplementedError

    def load_configuration(self):
        raise NotImplementedError

    def stop_network_monitor(self):
        raise NotImplementedError

    def subscribe_to_network_status(self):
        raise NotImplementedError

    @property
    def timeout_rd(self):
        return self.__timeout_rd

    @timeout_rd.setter
    def timeout_rd(self, value):
        self.__timeout_rd = value

    @property
    def timeout_wr(self):
        return self.__timeout_wr

    @timeout_wr.setter
    def timeout_wr(self, value):
        self.__timeout_wr = value