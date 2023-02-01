import struct
from enum import Enum

from ingenialink.enums.register import REG_DTYPE
from time import sleep

import warnings
import functools
import ingenialogger

logger = ingenialogger.get_logger(__name__)

POLLING_MAX_TRIES = 5  # Seconds

__dtype_value = {
    REG_DTYPE.U8: (1, False),
    REG_DTYPE.S8: (1, True),
    REG_DTYPE.U16: (2, False),
    REG_DTYPE.S16: (2, True),
    REG_DTYPE.U32: (4, False),
    REG_DTYPE.S32: (4, True),
    REG_DTYPE.U64: (8, False),
    REG_DTYPE.S64: (8, True),
    REG_DTYPE.FLOAT: (4, None),
}


def deprecated(custom_msg=None, new_func_name=None):
    """This is a decorator which can be used to mark functions as deprecated.
    It will result in a warning being emitted when the function is used. We use
    this decorator instead of any deprecation library because all libraries raise
    a DeprecationWarning but since by default this warning is hidden, we use this
    decorator to manually activate DeprecationWarning and turning it off after
    the warn has been done."""

    def wrap(func):
        @functools.wraps(func)
        def wrapped_method(*args, **kwargs):
            warnings.simplefilter("always", DeprecationWarning)  # Turn off filter
            msg = 'Call to deprecated function "{}".'.format(func.__name__)
            if new_func_name:
                msg += ' Please, use "{}" function instead.'.format(new_func_name)
            if custom_msg:
                msg = custom_msg
            warnings.warn(msg, category=DeprecationWarning, stacklevel=2)
            warnings.simplefilter("ignore", DeprecationWarning)  # Reset filter
            return func(*args, **kwargs)

        return wrapped_method

    return wrap


def to_ms(s):
    """Convert from seconds to milliseconds.

    Args:
        s (float, int): Value in seconds.

    Returns:
        int: Value in milliseconds.
    """
    return int(s * 1e3)


def wait_for_register_value(servo, subnode, register, expected_value):
    """Waits for the register to reach a value.

    Args:
        servo (Servo): Instance of the servo to be used.
        subnode (int): Target subnode.
        register (Register): Register to be read.
        expected_value (int, float, str): Expected value for the given register.

    Returns:
        int: Return code of the operation.
    """
    logger.debug("Waiting for register {} to return <{}>".format(register, expected_value))
    num_tries = 0
    r = -2
    while num_tries < POLLING_MAX_TRIES:

        value = None
        try:
            value = servo.read(register, subnode=subnode)
            r = 0
        except Exception as e:
            r = -1

        if r >= 0:
            if value == expected_value:
                logger.debug("Success. Read value {}.".format(value))
                break
            else:
                r = -2
        num_tries += 1
        logger.debug("Trying again {}. r: {}. value {}.".format(num_tries, r, value))
        sleep(1)

    return r


def count_file_lines(file_path):
    """Count how many lines the given file has.

    Args:
        file_path (str): Path to the target file.

    Returns:
        int: Number of lines in the file.

    """
    file = open(file_path, "r")
    total_lines = 0
    for _ in file:
        total_lines += 1
    file.close()
    return total_lines


def remove_xml_subelement(element, subelement):
    """Removes a subelement from the given element the element contains the subelement

    Args:
        element (Element): Element to be extracted from.
        subelement (Element): Element to be extracted.
    """
    if subelement is not None and subelement in element:
        element.remove(subelement)


def pop_element(dictionary, element):
    """Pops an element from a dictionary only if it is contained in it

    Args:
        dictionary (dict): Dictionary containing all the elment.s
        element (str): Element to be poped from the dictionary.
    """
    if element in dictionary:
        dictionary.pop(element)


def cleanup_register(register):
    """Cleans a ElementTree register to remove all
    unnecessary fields for a configuration file

    Args:
        register (Register): Register to be cleaned.
    """
    labels = register.find("./Labels")
    range = register.find("./Range")
    enums = register.find("./Enumerations")

    remove_xml_subelement(register, labels)
    remove_xml_subelement(register, enums)
    remove_xml_subelement(register, range)

    pop_element(register.attrib, "desc")
    pop_element(register.attrib, "cat_id")
    pop_element(register.attrib, "cyclic")
    pop_element(register.attrib, "units")
    pop_element(register.attrib, "address_type")

    register.text = ""


def get_drive_identification(servo, subnode=None):
    """Gets the identification information of a given subnode.

    Args:
        servo: Instance of the servo Class.
        subnode: subnode to be targeted.

    Returns:
        int, int: Product code and revision number of the targeted subnode.
    """
    prod_code = None
    re_number = None
    try:
        if subnode is None or subnode == 0:
            prod_code = servo.read("DRV_ID_PRODUCT_CODE_COCO", 0)
            re_number = servo.read("DRV_ID_REVISION_NUMBER_COCO", 0)
        else:
            prod_code = servo.read("DRV_ID_PRODUCT_CODE", subnode=subnode)
            re_number = servo.read("DRV_ID_REVISION_NUMBER", subnode)
    except Exception as e:
        pass

    return prod_code, re_number


def convert_ip_to_int(ip):
    """Converts a string type IP to its integer value.

    Args:
        ip (str): IP to be converted.

    """
    split_ip = ip.split(".")
    drive_ip1 = int(split_ip[0]) << 24
    drive_ip2 = int(split_ip[1]) << 16
    drive_ip3 = int(split_ip[2]) << 8
    drive_ip4 = int(split_ip[3])
    return drive_ip1 + drive_ip2 + drive_ip3 + drive_ip4


def convert_int_to_ip(int_ip):
    """Converts an integer type IP to its string form.

    Args:
        int_ip (int): IP to be converted.

    """
    drive_ip1 = (int_ip >> 24) & 0x000000FF
    drive_ip2 = (int_ip >> 16) & 0x000000FF
    drive_ip3 = (int_ip >> 8) & 0x000000FF
    drive_ip4 = int_ip & 0x000000FF
    return "{}.{}.{}.{}".format(drive_ip1, drive_ip2, drive_ip3, drive_ip4)


class INT_SIZES(Enum):
    """Integer sizes."""

    S8_MIN = -128
    S16_MIN = -32767 - 1
    S32_MIN = -2147483647 - 1
    S64_MIN = 9223372036854775807 - 1

    S8_MAX = 127
    S16_MAX = 32767
    S32_MAX = 2147483647
    S64_MAX = 9223372036854775807

    U8_MAX = 255
    U16_MAX = 65535
    U32_MAX = 4294967295
    U64_MAX = 18446744073709551615


def convert_bytes_to_dtype(data, dtype):
    """Convert data in bytes to corresponding dtype."""
    if dtype in __dtype_value:
        bytes_length, signed = __dtype_value[dtype]
        data = data[:bytes_length]

    if dtype == REG_DTYPE.FLOAT:
        [value] = struct.unpack("f", data)
    elif dtype == REG_DTYPE.STR:
        value = data.decode("utf-8").rstrip("\0")
    else:
        value = int.from_bytes(data, "little", signed=signed)
    return value


def convert_dtype_to_bytes(data, dtype):
    """Convert data in dtype to bytes.
    Args:
        data: Data to convert.
        dtype (REG_DTYPE): Data type.
    """
    if dtype == REG_DTYPE.DOMAIN:
        return data
    if dtype == REG_DTYPE.FLOAT:
        return struct.pack("f", float(data))
    if dtype == REG_DTYPE.STR:
        return data.encode("utf_8")
    bytes_length, signed = __dtype_value[dtype]
    data = data.to_bytes(bytes_length, byteorder="little", signed=signed)
    return data
