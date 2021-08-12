from ..network import Network, NET_PROT
from ..utils._utils import *
from .._ingenialink import lib, ffi


class SerialNetwork(Network):
    def __init__(self, port=None, timeout_rd=0.5, timeout_wr=0.5):
        super(SerialNetwork, self).__init__()
        self.__port = port
        self.__timeout_rd = timeout_rd
        self.__timeout_wr = timeout_wr

    def devices(self, prot):
        """
        Obtain a list of network devices.
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

    def load_firmware(self, fw_file):
        # TODO: Implement firmware loader
        raise NotImplementedError

    def scan_slaves(self):
        raise NotImplementedError

    def connect_to_slave(self):
        raise NotImplementedError

    def disconnect_from_slave(self, servo):
        raise NotImplementedError

    @property
    def protocol(self):
        """NET_PROT: Obtain network protocol."""
        return NET_PROT.MCB

    @property
    def port(self):
        return self.__port

    @port.setter
    def port(self, value):
        self.__port = value

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