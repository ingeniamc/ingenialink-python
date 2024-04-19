import functools
import logging
import struct
import warnings
import xml.etree.ElementTree as ET
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple, Union

import ingenialogger

from ingenialink.enums.register import REG_DTYPE
from ingenialink.exceptions import ILValueError

if TYPE_CHECKING:
    from ingenialink.servo import Servo


logger = ingenialogger.get_logger(__name__)

POLLING_MAX_TRIES = 5  # Seconds

dtype_value: Dict[REG_DTYPE, Tuple[int, bool]] = {
    REG_DTYPE.U8: (1, False),
    REG_DTYPE.S8: (1, True),
    REG_DTYPE.U16: (2, False),
    REG_DTYPE.S16: (2, True),
    REG_DTYPE.U32: (4, False),
    REG_DTYPE.S32: (4, True),
    REG_DTYPE.U64: (8, False),
    REG_DTYPE.S64: (8, True),
    REG_DTYPE.FLOAT: (4, True),
    REG_DTYPE.BOOL: (1, False),
}

dtype_length_bits: Dict[REG_DTYPE, int] = {
    REG_DTYPE.U8: 8,
    REG_DTYPE.S8: 8,
    REG_DTYPE.U16: 16,
    REG_DTYPE.S16: 16,
    REG_DTYPE.U32: 32,
    REG_DTYPE.S32: 32,
    REG_DTYPE.U64: 64,
    REG_DTYPE.S64: 64,
    REG_DTYPE.FLOAT: 32,
    REG_DTYPE.BOOL: 1,
}

VALID_BIT_REGISTER_VALUES = [0, 1, True, False]


def deprecated(
    custom_msg: Optional[str] = None, new_func_name: Optional[str] = None
) -> Callable[..., Any]:
    """This is a decorator which can be used to mark functions as deprecated.
    It will result in a warning being emitted when the function is used. We use
    this decorator instead of any deprecation library because all libraries raise
    a DeprecationWarning but since by default this warning is hidden, we use this
    decorator to manually activate DeprecationWarning and turning it off after
    the warn has been done."""

    def wrap(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapped_method(*args: Any, **kwargs: Any) -> Any:
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


class DisableLogger:
    """Context manager to disable all logs."""

    def __enter__(self) -> None:
        logging.disable(logging.CRITICAL)

    def __exit__(self, *args: Any) -> None:
        logging.disable(logging.NOTSET)


def to_ms(s: Union[int, float]) -> int:
    """Convert from seconds to milliseconds.

    Args:
        s: Value in seconds.

    Returns:
        Value in milliseconds.
    """
    return int(s * 1e3)


def remove_xml_subelement(element: ET.Element, subelement: ET.Element) -> None:
    """Removes a subelement from the given element the element contains the subelement

    Args:
        element: Element to be extracted from.
        subelement: Element to be extracted.
    """
    if subelement is not None and subelement in element:
        element.remove(subelement)


def pop_element(dictionary: Dict[str, Any], element: str) -> None:
    """Pops an element from a dictionary only if it is contained in it

    Args:
        dictionary: Dictionary containing all the elements
        element: Element to be popped from the dictionary.
    """
    if element in dictionary:
        dictionary.pop(element)


def cleanup_register(register: ET.Element) -> None:
    """Cleans a ElementTree register to remove all
    unnecessary fields for a configuration file

    Args:
        register: Register to be cleaned.
    """
    labels = register.find("./Labels")
    range = register.find("./Range")
    enums = register.find("./Enumerations")

    if labels:
        remove_xml_subelement(register, labels)
    if enums:
        remove_xml_subelement(register, enums)
    if range:
        remove_xml_subelement(register, range)

    pop_element(register.attrib, "desc")
    pop_element(register.attrib, "cat_id")
    pop_element(register.attrib, "cyclic")
    pop_element(register.attrib, "units")
    pop_element(register.attrib, "address_type")

    register.text = ""


def get_drive_identification(
    servo: "Servo", subnode: Optional[int] = None
) -> Tuple[Optional[int], Optional[int]]:
    """Gets the identification information of a given subnode.

    Args:
        servo: Instance of the servo Class.
        subnode: subnode to be targeted.

    Returns:
        int, Product code and revision number of the targeted subnode.
    """
    prod_code = None
    re_number = None
    try:
        if subnode is None or subnode == 0:
            prod_code = int(servo.read("DRV_ID_PRODUCT_CODE_COCO", 0))
            re_number = int(servo.read("DRV_ID_REVISION_NUMBER_COCO", 0))
        else:
            prod_code = int(servo.read("DRV_ID_PRODUCT_CODE", subnode=subnode))
            re_number = int(servo.read("DRV_ID_REVISION_NUMBER", subnode))
    except Exception as e:
        pass

    return prod_code, re_number


def convert_ip_to_int(ip: str) -> int:
    """Converts a string type IP to its integer value.

    Args:
        ip: IP to be converted.

    """
    split_ip = ip.split(".")
    drive_ip1 = int(split_ip[0]) << 24
    drive_ip2 = int(split_ip[1]) << 16
    drive_ip3 = int(split_ip[2]) << 8
    drive_ip4 = int(split_ip[3])
    return drive_ip1 + drive_ip2 + drive_ip3 + drive_ip4


def convert_int_to_ip(int_ip: int) -> str:
    """Converts an integer type IP to its string form.

    Args:
        int_ip: IP to be converted.

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


def convert_bytes_to_dtype(data: bytes, dtype: REG_DTYPE) -> Union[float, int, str]:
    """Convert data in bytes to corresponding dtype.

    Args:
        data: data to convert
        dtype: output dtype

    Raises:
        ILValueError: If data can't be decoded in utf-8
    """
    signed = False
    if dtype in dtype_value:
        bytes_length, signed = dtype_value[dtype]
        data = data[:bytes_length]

    if dtype == REG_DTYPE.FLOAT:
        [value] = struct.unpack("f", data)
        if not isinstance(value, float):
            raise ILValueError(f"Data could not be converted to float. Obtained: {value}")
    elif dtype == REG_DTYPE.STR:
        try:
            value = data.split(b"\x00")[0].decode("utf-8")
        except UnicodeDecodeError as e:
            raise ILValueError(f"Can't decode {e.object!r} to utf-8 string") from e
    else:
        value = int.from_bytes(data, "little", signed=signed)
    if dtype == REG_DTYPE.BOOL:
        value = bool(value)
    if not isinstance(value, (int, float, str)):
        raise ILValueError(f"Bad data type: {type(value)}")
    return value


def convert_dtype_to_bytes(data: Union[int, float, str, bytes], dtype: REG_DTYPE) -> bytes:
    """Convert data in dtype to bytes.
    Args:
        data: Data to convert.
        dtype: Data type.
    """
    if (
        dtype == REG_DTYPE.BOOL
        and data not in VALID_BIT_REGISTER_VALUES
        and not isinstance(data, bytes)
    ):
        raise ValueError(f"Invalid value. Expected values: {VALID_BIT_REGISTER_VALUES}, got {data}")
    if dtype == REG_DTYPE.BYTE_ARRAY_512:
        if not isinstance(data, bytes):
            raise ValueError(f"Expected data of type bytes, but got {type(data)}")
        return data
    if dtype == REG_DTYPE.FLOAT:
        if not isinstance(data, (float, int)):
            raise ValueError(f"Expected data of type float, but got {type(data)}")
        return struct.pack("f", float(data))
    if dtype == REG_DTYPE.STR:
        if not isinstance(data, str):
            raise ValueError(f"Expected data of type string, but  got {type(data)}")
        return data.encode("utf_8")
    if not isinstance(data, int):
        raise ValueError(f"Expected data of type int, but {type(data)}")
    bytes_length, signed = dtype_value[dtype]
    data_bytes = data.to_bytes(bytes_length, byteorder="little", signed=signed)
    return data_bytes
