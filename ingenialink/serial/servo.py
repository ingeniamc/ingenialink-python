from ingenialink.ipb.servo import IPBServo
from .._ingenialink import lib, ffi
from ingenialink.utils._utils import pstr, cstr, raise_null, to_ms

import ingenialogger
logger = ingenialogger.get_logger(__name__)


class SerialServo(IPBServo):
    """Servo object for all the Serial slave functionalities.

    Args:
        cffi_net (CData): CData instance of the network.
        target (int): Target ID for the slave.
        dictionary_path (str): Path to the dictionary.

    """
    def __init__(self, cffi_net, target, dictionary_path):
        _dictionary = cstr(dictionary_path) if dictionary_path else ffi.NULL
        servo = lib.il_servo_create(cffi_net, target, _dictionary)
        raise_null(servo)

        cffi_servo = ffi.gc(servo, lib.il_servo_destroy)
        super(SerialServo, self).__init__(cffi_servo, target, dictionary_path)
