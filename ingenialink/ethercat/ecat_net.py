from ..net import Network
from .ecat_servo import EthercatServo
from ingenialink.utils._utils import cstr, pstr, raise_null, raise_err, to_ms
from .._ingenialink import lib, ffi


class EthercatNetwork(Network):
    def __init__(self, interface_name=""):
        self.__interface_name = interface_name

        self._net = ffi.new('il_net_t **')

    def load_firmware(self, fw_file):
        # TODO: Implement FOE fw loader
        raise NotImplementedError

    def scan_nodes(self):
        raise NotImplementedError


    """
    - boot_in_app:  If summit series -> True
                    If capitan series -> False
                    If custom device -> Contact manufacturer
    """
    def connect_to_slave(self, dict_f="", slave=1, boot_in_app=True):


        # r = servo.connect_ecat(ifname=ifname,
        #         #                        slave=slave,
        #         #                        use_eoe_comms=use_eoe_comms)
        _interface_name = cstr(self.__interface_name) if self.__interface_name else ffi.NULL
        self.slave = slave

        r = lib.il_servo_connect_ecat(3, self.ifname, self.net._net,
                                      self._servo, self.dict_f, 1061,
                                      self.slave, use_eoe_comms)
        time.sleep(2)
        return r

        if r <= 0:
            servo = None
            net = None
            raise_err(r)
        else:
            net._net = ffi.cast('il_net_t *', net._net[0])
            servo = EthercatServo._from_existing(servo_, dict_f)
            servo._servo = ffi.cast('il_servo_t *', servo._servo[0])
            servo.net = net

        return servo, net



    servo, net = il.servo.connect_ecat(
        "\\Device\\NPF_{43144EC3-59EF-408B-8D9B-4867F1324D62}",
        "resources/eve-net_1.7.1.xdf",
        1, use_eoe_comms=0)


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
    def interface_name(self):
        return self.__interface_name

    @interface_name.setter
    def interface_name(self, value):
        self.__interface_name = value





