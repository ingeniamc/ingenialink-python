from ..net import Network
from .ecat_servo import EthercatServo
from ingenialink.utils._utils import cstr, pstr, raise_null, raise_err, to_ms
from .._ingenialink import lib, ffi


class EthercatNetwork(Network):
    def __init__(self, interface_name=""):
        self.__interface_name = interface_name

        self.__net = ffi.new('il_net_t **')

    """
        - boot_in_app:  If summit series -> True
                        If capitan series -> False
                        If custom device -> Contact manufacturer
        """
    def load_firmware(self, fw_file, slave=1, boot_in_app=True):
        # TODO: Implement FOE fw loader
        raise NotImplementedError

    def scan_nodes(self):
        raise NotImplementedError

    def connect_to_slave(self, dictionary="", slave=1, use_eoe_comms=1):
        _interface_name = cstr(self.__interface_name) if self.__interface_name else ffi.NULL
        _dictionary = cstr(dictionary) if dictionary else ffi.NULL

        _servo = ffi.new('il_servo_t **')

        r = lib.il_servo_connect_ecat(3, _interface_name, self.__net,
                                      _servo, _dictionary, 1061,
                                      slave, use_eoe_comms)

        if r <= 0:
            _servo = None
            self.__net = None
            raise_err(r)
        else:
            self.__net = ffi.cast('il_net_t *', self.__net[0])
            servo = EthercatServo._from_existing(_servo, _dictionary)
            servo._servo = ffi.cast('il_servo_t *', servo._servo[0])
            servo.net = self.__net

        return servo


    def disconnect(self):
        return lib.il_net_master_stop(self.__net)

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
    def interface_name(self):
        return self.__interface_name

    @interface_name.setter
    def interface_name(self, value):
        self.__interface_name = value





