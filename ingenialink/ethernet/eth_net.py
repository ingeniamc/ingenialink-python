from ..net import Network, NET_PROT, NET_TRANS_PROT
from .eth_servo import EthernetServo
from .._utils import cstr, pstr, raise_null, raise_err, to_ms
from .._ingenialink import lib, ffi


class EthernetNetwork(Network):
    def __init__(self):
        self.__net = None
        opts = ffi.new('il_net_opts_t *')
        self._net = lib.il_net_create(NET_PROT.ETH.value, opts)
        raise_null(self._net)

    def load_fw(self, fw_file):
        # TODO: Implement FTP fw loader
        raise NotImplementedError

    def scan_nodes(self):
        raise NotImplementedError

    def connect_to_slave(self, target, dictionary=None, port=1061,
                communication_protocol=NET_TRANS_PROT.UDP):
        net__ = ffi.new('il_net_t **')
        servo__ = ffi.new('il_servo_t **')
        _dictionary = cstr(dictionary) if dictionary else ffi.NULL
        _target = cstr(target) if target else ffi.NULL

        r = lib.il_servo_lucky_eth(NET_PROT.ETH.value, net__, servo__,
                                   _dictionary, _target,
                                   port, communication_protocol.value)

        raise_err(r)

        net_ = ffi.cast('il_net_t *', net__[0])
        servo_ = ffi.cast('il_servo_t *', servo__[0])

        net = Network._from_existing(net_)
        servo = EthernetServo._from_existing(servo_, _dictionary)
        servo.net = net
        servo.target = target
        servo.dictionary = dictionary
        servo.port = port
        servo.communication_protocol = communication_protocol

        self.__net = net
        self.servos.append(servo)

        return r, servo

    def disconnect_from_slave(self, servo):
        raise NotImplementedError

    # Properties
    @property
    def net(self):
        return self.__net

    @net.setter
    def net(self, value):
        self.__net = value
