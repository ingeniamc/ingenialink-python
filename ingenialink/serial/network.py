from ingenialink.network import NET_PROT
from ingenialink.ipb.network import IPBNetwork
from .._ingenialink import lib, ffi
from ingenialink.utils._utils import pstr, cstr, raise_null, to_ms
from ingenialink.serial.servo import SerialServo


class SerialNetwork(IPBNetwork):
    def __init__(self, timeout_rd=0.5, timeout_wr=0.5):
        super(SerialNetwork, self).__init__()
        self.__timeout_rd = timeout_rd
        self.__timeout_wr = timeout_wr

        self.__net_interface = None

    def load_firmware(self, fw_file):
        raise NotImplementedError

    def scan_slaves(self):
        """Obtain a list of network devices.

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

    def connect_to_slave(self, target=None, dictionary=""):
        self._on_found = ffi.NULL

        callback = ffi.NULL
        handle = ffi.NULL

        opts = ffi.new('il_net_opts_t *')
        _port = ffi.new('char []', cstr(target))
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

        servo = None
        if len(found) > 0:
            servo = SerialServo(net=self.__net_interface, target=found[0],
                            dictionary_path=dictionary)
            self._cffi_network = self.__net_interface
            self.servos.append(servo)
        return servo

    def disconnect_from_slave(self, servo):
        self.servos.remove(servo)
        if len(self.servos) == 0:
            lib.il_net_disconnect(self._cffi_network)
            self.destroy_network()
        self._cffi_network = None


    def stop_network_monitor(self):
        raise NotImplementedError

    def subscribe_to_status(self, callback):
        raise NotImplementedError

    def unsubscribe_from_status(self, callback):
        raise NotImplementedError

    @property
    def protocol(self):
        """NET_PROT: Obtain network protocol."""
        return NET_PROT.MCB

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
