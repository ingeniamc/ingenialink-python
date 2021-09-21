from .._ingenialink import lib, ffi
from ingenialink.ipb.servo import IPBServo
from ingenialink.utils._utils import cstr, raise_null
from ingenialink.ipb.register import IPBRegister, REG_ACCESS, REG_DTYPE

import ingenialogger
logger = ingenialogger.get_logger(__name__)


PRODUCT_ID_MOCO = IPBRegister(
    identifier='', units='', subnode=1, address=0x06E1, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
)

SERIAL_NUMBER_MOCO = IPBRegister(
    identifier='', units='', subnode=1, address=0x06E6, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
)

REV_NUMBER_MOCO = IPBRegister(
    identifier='', units='', subnode=1, address=0x06E2, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
)


class SerialServo(IPBServo):
    """Servo object for all the Serial slave functionalities.

    Args:
        cffi_net (CData): CData instance of the network.
        target (str): Target ID for the slave.
        slave_num (int): Slave number.
        dictionary_path (str): Path to the dictionary.

    """
    def __init__(self, cffi_net, target, slave_num, dictionary_path):
        _dictionary = cstr(dictionary_path) if dictionary_path else ffi.NULL
        servo = lib.il_servo_create(cffi_net, slave_num, _dictionary)
        raise_null(servo)

        cffi_servo = ffi.gc(servo, lib.il_servo_destroy)
        super(SerialServo, self).__init__(
            cffi_servo, cffi_net, target, dictionary_path)

    @property
    def info(self):
        """dict: Servo information."""
        sw_version = '-'
        try:
            serial_number = self.read(SERIAL_NUMBER_MOCO)
        except Exception:
            serial_number = '-'
        try:
            product_code = self.read(PRODUCT_ID_MOCO)
        except Exception:
            product_code = '-'
        try:
            revision_number = self.read(REV_NUMBER_MOCO)
        except Exception:
            revision_number = '-'
        hw_variant = 'A'

        return {
            'name': self.name,
            'serial_number': serial_number,
            'firmware_version': sw_version,
            'product_code': product_code,
            'revision_number': revision_number,
            'hw_variant': hw_variant
        }
