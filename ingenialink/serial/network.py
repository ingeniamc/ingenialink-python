from ingenialink.network import NET_PROT
from ingenialink.ipb.network import IPBNetwork
from .._ingenialink import lib, ffi
from ingenialink.utils._utils import pstr, cstr, raise_null, to_ms
from ingenialink.serial.servo import SerialServo


class SerialNetwork(IPBNetwork):
    """Network for all Serial communications.

    Args:
        timeout_rd (int): Timeout for read commands.
        timeout_wr (int): Timeout for write commands.

    """
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
        """Connects to a slave through the given network settings.

        Args:
            target (str): IP of the target slave.
            dictionary (str): Path to the target dictionary file.

        Returns:
            SerialServo: Instance of the servo connected.

        """
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
        if found:
            servo = SerialServo(self.__net_interface, found[0], dictionary)
            self._cffi_network = self.__net_interface
            self.servos.append(servo)
        return servo

    def disconnect_from_slave(self, servo):
        """Disconnects the slave from the network.

        Args:
            servo (SerialServo): Instance of the servo connected.

        """
        self.servos.remove(servo)
        if len(self.servos) == 0:
            lib.il_net_disconnect(self._cffi_network)
            self.destroy_network()
        self._cffi_network = None

    @property
    def protocol(self):
        """NET_PROT: Obtain network protocol."""
        return NET_PROT.MCB

    @property
    def timeout_rd(self):
        """int: Read timeout"""
        return self.__timeout_rd

    @timeout_rd.setter
    def timeout_rd(self, value):
        self.__timeout_rd = value

    @property
    def timeout_wr(self):
        """int: Write timeout"""
        return self.__timeout_wr

    @timeout_wr.setter
    def timeout_wr(self, value):
        self.__timeout_wr = value
