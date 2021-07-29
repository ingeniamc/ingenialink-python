from ..net import Network, NET_PROT, NET_TRANS_PROT
from ..servo import Servo
from .._utils import cstr, pstr, raise_null, raise_err, to_ms
from .._ingenialink import lib, ffi


class EthercatServo(Servo):
    def __init__(self, net):
        self.__net = net

    def is_alive(self):
        raise NotImplementedError

    def restore_parameters(self):
        raise NotImplementedError

    def store_parameters(self):
        raise NotImplementedError

    @property
    def net(self):
        return self.__net

    @net.setter
    def net(self, value):
        self.__net = value