from ..net import Network, NET_PROT, NET_TRANS_PROT
from ..servo import Servo
from .._utils import cstr, pstr, raise_null, raise_err, to_ms
from .._ingenialink import lib, ffi


class EthernetNetwork(Network):
    def __init__(self, address_ip=None, dict_f=None, port_ip=1061, protocol=2):
        self.__address_ip = address_ip
        self.__dict_f = dict_f
        self.__port_ip = port_ip
        self.__protocol = protocol
        self.__net = None
        self.__servos = []

        opts = ffi.new('il_net_opts_t *')
        self._net = lib.il_net_create(NET_PROT.ETH.value, opts)
        raise_null(self._net)

    def load_fw(self, fw_file):
        # TODO: Implement FTP fw loader
        raise NotImplementedError

    def scan_nodes(self):
        raise NotImplementedError

    def connect(self):
        net__ = ffi.new('il_net_t **')
        servo__ = ffi.new('il_servo_t **')
        dict_f = cstr(self.__dict_f) if self.__dict_f else ffi.NULL
        address_ip = cstr(self.__address_ip) if self.__address_ip else ffi.NULL

        r = lib.il_servo_lucky_eth(NET_PROT.ETH.value, net__, servo__, dict_f,
                                   address_ip, self.__port_ip, self.__protocol)

        raise_err(r)

        net_ = ffi.cast('il_net_t *', net__[0])
        servo_ = ffi.cast('il_servo_t *', servo__[0])

        net = Network._from_existing(net_)
        servo = Servo._from_existing(servo_, dict_f)
        servo.net = net

        self.__net = net
        self.__servos.append(servo)

        return r, servo

    def disconnect(self):
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
    def address_ip(self):
        return self.__address_ip

    @address_ip.setter
    def address_ip(self, value):
        self.__address_ip = value

    @property
    def dict_f(self):
        return self.__dict_f

    @dict_f.setter
    def dict_f(self, value):
        self.__dict_f = value

    @property
    def port_ip(self):
        return self.__port_ip

    @port_ip.setter
    def port_ip(self, value):
        self.__port_ip = value

    @property
    def protocol(self):
        return self.__protocol

    @protocol.setter
    def protocol(self, value):
        self.__protocol = value


