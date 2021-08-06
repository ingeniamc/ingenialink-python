from ..servo import Servo


class EthercatServo(Servo):
    def __init__(self, net):
        self.__net = net

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