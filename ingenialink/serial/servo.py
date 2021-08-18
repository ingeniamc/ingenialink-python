from ingenialink.ipb.servo import IPBServo
from .._ingenialink import lib, ffi
from ingenialink.utils._utils import pstr, cstr, raise_null, to_ms

import ingenialogger
logger = ingenialogger.get_logger(__name__)


class SerialServo(IPBServo):
    """Servo object for all the Serial slave functionalities.

    Args:
        net (IPBNetwork): IPB Network associated with the servo.
        target (str): Target ID for the slave.
        dictionary_path (str): Path to the dictionary.
    """
    def __init__(self, net, target, dictionary_path):
        super(SerialServo, self).__init__(net, target, dictionary_path)
        if target:
            _dictionary = cstr(dictionary_path) if dictionary_path else ffi.NULL
            servo = lib.il_servo_create(net, target, _dictionary)
            raise_null(servo)

            self._cffi_servo = ffi.gc(servo, lib.il_servo_destroy)
