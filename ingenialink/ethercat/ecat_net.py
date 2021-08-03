from ..net import Network
from .._ingenialink import lib, ffi


class EthercatNetwork(Network):
    def __init__(self, if_name="", dict_f="", slave=1, is_summit=True):
        self.__if_name = if_name
        self.__dict_f = dict_f
        self.__slave = slave
        self.__is_summit = is_summit

        self._net = ffi.new('il_net_t **')

    def load_firmware(self, fw_file):
        # TODO: Implement FTP fw loader
        raise NotImplementedError

    def scan_nodes(self):
        raise NotImplementedError

    def connect(self):
        raise NotImplementedError

    def disconnect(self):
        return lib.il_net_master_stop(self._net)

    def is_alive(self):
        raise NotImplementedError

    # Properties
    @property
    def net(self):
        return self.__net

    @net.setter
    def net(self, value):
        self.__net = value

    @property
    def servos(self):
        return self.__servos

    @servos.setter
    def servos(self, value):
        self.__servos = value

    @property
    def if_name(self):
        return self.__if_name

    @if_name.setter
    def if_name(self, value):
        self.__if_name = value

    @property
    def dict_f(self):
        return self.__dict_f

    @dict_f.setter
    def dict_f(self, value):
        self.__dict_f = value

    @property
    def slave(self):
        return self.__slave

    @slave.setter
    def slave(self, value):
        self.__slave = value

    @property
    def is_summit(self):
        return self.__is_summit

    @is_summit.setter
    def is_summit(self, value):
        self.__is_summit = value





