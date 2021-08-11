from ingenialink.utils._utils import cstr
from ..servo import Servo
from .._ingenialink import lib, ffi


class EthercatServo(Servo):
    def __init__(self, net, target, dictionary_path):
        super(EthercatServo, self).__init__(net, target)
        self._dictionary = cstr(dictionary_path) if dictionary_path else ffi.NULL
        self.__net = net

        if not hasattr(self, '_errors') or not self._errors:
            self._errors = self._get_all_errors(self._dictionary)

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
