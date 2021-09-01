from ingenialink.ipb.servo import IPBServo
from .._ingenialink import lib, ffi

import ingenialogger
logger = ingenialogger.get_logger(__name__)


class EthercatServo(IPBServo):
    """Servo object for all the EtherCAT slave functionalities.

    Args:
        cffi_servo (CData): CData instance of the servo.
        cffi_net (CData): CData instance of the network.
        target (int): Target ID for the slave.
        dictionary_path (str): Path to the dictionary.

    """
    def __init__(self, cffi_servo, cffi_net, target, dictionary_path=None):
        servo = ffi.gc(cffi_servo, lib.il_servo_fake_destroy)
        super(EthercatServo, self).__init__(
            servo, cffi_net, target, dictionary_path)
