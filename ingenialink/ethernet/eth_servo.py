from ..net import Network, NET_PROT, NET_TRANS_PROT
from ..servo import Servo
from ingenialink.utils._utils import cstr, pstr, raise_null, raise_err, to_ms
from .._ingenialink import lib, ffi


class EthernetServo(Servo):
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

    @property
    def target(self):
        return self.__target

    @target.setter
    def target(self, value):
        self.__target = value

    @property
    def dictionary(self):
        return self.__dictionary

    @dictionary.setter
    def dictionary(self, value):
        self.__dictionary = value

    @property
    def port(self):
        return self.__port

    @port.setter
    def port(self, value):
        self.__port = value

    @property
    def communication_protocol(self):
        return self.__communication_protocol

    @communication_protocol.setter
    def communication_protocol(self, value):
        self.__communication_protocol = value