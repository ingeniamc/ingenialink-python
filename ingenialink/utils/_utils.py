import functools
import logging
import struct
import warnings
import weakref
from typing import Any, Callable, Optional, Union
from xml.etree import ElementTree

import ingenialogger

from ingenialink.enums.register import RegDtype
from ingenialink.exceptions import ILValueError

logger = ingenialogger.get_logger(__name__)

POLLING_MAX_TRIES = 5  # Seconds

# Mapping type -> [Number of bytes, signedness]
dtype_value: dict[RegDtype, tuple[int, bool]] = {
    RegDtype.U8: (1, False),
    RegDtype.S8: (1, True),
    RegDtype.U16: (2, False),
    RegDtype.S16: (2, True),
    RegDtype.U32: (4, False),
    RegDtype.S32: (4, True),
    RegDtype.U64: (8, False),
    RegDtype.S64: (8, True),
    RegDtype.FLOAT: (4, True),
    RegDtype.BOOL: (1, False),
}

dtype_length_bits: dict[RegDtype, int] = {
    RegDtype.U8: 8,
    RegDtype.S8: 8,
    RegDtype.U16: 16,
    RegDtype.S16: 16,
    RegDtype.U32: 32,
    RegDtype.S32: 32,
    RegDtype.U64: 64,
    RegDtype.S64: 64,
    RegDtype.FLOAT: 32,
    RegDtype.BOOL: 1,
}

VALID_BIT_REGISTER_VALUES = [0, 1, True, False]


def deprecated(
    custom_msg: Optional[str] = None, new_func_name: Optional[str] = None
) -> Callable[..., Any]:
    """Deprecated decorator.

    This is a decorator which can be used to mark functions as deprecated.
    It will result in a warning being emitted when the function is used. We use
    this decorator instead of any deprecation library because all libraries raise
    a DeprecationWarning but since by default this warning is hidden, we use this
    decorator to manually activate DeprecationWarning and turning it off after
    the warn has been done.

    Returns:
        wrapped method.
    """

    def wrap(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapped_method(*args: Any, **kwargs: Any) -> Any:
            warnings.simplefilter("always", DeprecationWarning)  # Turn off filter
            msg = f'Call to deprecated function "{func.__name__}".'
            if new_func_name:
                msg += f' Please, use "{new_func_name}" function instead.'
            if custom_msg:
                msg = custom_msg
            warnings.warn(msg, category=DeprecationWarning, stacklevel=2)
            warnings.simplefilter("ignore", DeprecationWarning)  # Reset filter
            return func(*args, **kwargs)

        return wrapped_method

    return wrap


def weak_lru(maxsize: int = 128, typed: bool = False) -> Callable[..., Any]:
    """Decorator that allows safe use of lru_cache in class methods.

    Args:
        maxsize: maximum size. Defaults to 128.
        typed: typed. Defaults to False.

    Returns:
        wrapped method.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        ref = weakref.ref

        @functools.lru_cache(maxsize, typed)
        def _func(_self: Any, /, *args: Any, **kwargs: Any) -> Any:
            return func(_self(), *args, **kwargs)

        @functools.wraps(func)
        def wrapper(self: Any, /, *args: Any, **kwargs: Any) -> Any:
            return _func(ref(self), *args, **kwargs)

        return wrapper

    return decorator


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


def remove_xml_subelement(element: ElementTree.Element, subelement: ElementTree.Element) -> None:
    """Removes a subelement from the given element the element contains the subelement.

    Args:
        element: Element to be extracted from.
        subelement: Element to be extracted.
    """
    if subelement is not None and subelement in element:
        element.remove(subelement)


def pop_element(dictionary: dict[str, Any], element: str) -> None:
    """Pops an element from a dictionary only if it is contained in it.

    Args:
        dictionary: Dictionary containing all the elements
        element: Element to be popped from the dictionary.
    """
    if element in dictionary:
        dictionary.pop(element)


def cleanup_register(register: ElementTree.Element) -> None:
    """Clean a register element.

    Cleans a ElementTree register to remove all
    unnecessary fields for a configuration file.

    Args:
        register: Register to be cleaned.
    """
    labels = register.find("./Labels")
    reg_range = register.find("./Range")
    enums = register.find("./Enumerations")

    if labels:
        remove_xml_subelement(register, labels)
    if enums:
        remove_xml_subelement(register, enums)
    if reg_range:
        remove_xml_subelement(register, reg_range)

    pop_element(register.attrib, "desc")
    pop_element(register.attrib, "cat_id")
    pop_element(register.attrib, "pdo_access")
    pop_element(register.attrib, "units")
    pop_element(register.attrib, "address_type")

    register.text = ""


def convert_ip_to_int(ip: str) -> int:
    """Converts a string type IP to its integer value.

    Args:
        ip: IP to be converted.

    Returns:
        IP in integer form.
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

    Returns:
        IP in string form.
    """
    drive_ip1 = (int_ip >> 24) & 0x000000FF
    drive_ip2 = (int_ip >> 16) & 0x000000FF
    drive_ip3 = (int_ip >> 8) & 0x000000FF
    drive_ip4 = int_ip & 0x000000FF
    return f"{drive_ip1}.{drive_ip2}.{drive_ip3}.{drive_ip4}"


def convert_bytes_to_dtype(data: bytes, dtype: RegDtype) -> Union[float, int, str, bytes]:
    """Convert data in bytes to corresponding dtype.

    Bytes have to be ordered in LSB.

    Args:
        data: data to convert
        dtype: output dtype

    Returns:
        Value formatted in data type

    Raises:
        ILValueError: If data can't be decoded in utf-8
    """
    signed = False
    if dtype in dtype_value:
        bytes_length, signed = dtype_value[dtype]
        data = data[:bytes_length]

    if dtype == RegDtype.FLOAT:
        [value] = struct.unpack("f", data)
        if not isinstance(value, float):
            raise ILValueError(f"Data could not be converted to float. Obtained: {value}")
    elif dtype == RegDtype.STR:
        try:
            value = data.split(b"\x00")[0].decode("utf-8")
        except UnicodeDecodeError as e:
            raise ILValueError(f"Can't decode {e.object!r} to utf-8 string") from e
    elif dtype == RegDtype.BYTE_ARRAY_512:
        return data
    else:
        value = int.from_bytes(data, "little", signed=signed)
    if dtype == RegDtype.BOOL:
        value = bool(value)
    if not isinstance(value, (int, float, str)):
        raise ILValueError(f"Bad data type: {type(value)}")
    return value


def convert_dtype_to_bytes(data: Union[int, float, str, bytes], dtype: RegDtype) -> bytes:
    """Convert data in dtype to bytes.

    Bytes will be ordered in LSB.

    Args:
        data: Data to convert.
        dtype: Data type.

    Raises:
        ValueError: if the data has an invalid value.

    Returns:
        Value formatted to bytes
    """
    if (
        dtype == RegDtype.BOOL
        and data not in VALID_BIT_REGISTER_VALUES
        and not isinstance(data, bytes)
    ):
        raise ValueError(f"Invalid value. Expected values: {VALID_BIT_REGISTER_VALUES}, got {data}")
    if dtype == RegDtype.BYTE_ARRAY_512:
        if not isinstance(data, bytes):
            raise ValueError(f"Expected data of type bytes, but got {type(data)}")
        return data
    if dtype == RegDtype.FLOAT:
        if not isinstance(data, (float, int)):
            raise ValueError(f"Expected data of type float, but got {type(data)}")
        return struct.pack("f", float(data))
    if dtype == RegDtype.STR:
        if not isinstance(data, str):
            raise ValueError(f"Expected data of type string, but  got {type(data)}")
        return data.encode("utf_8")
    if not isinstance(data, int):
        raise ValueError(f"Expected data of type int, but {type(data)}")
    bytes_length, signed = dtype_value[dtype]
    data_bytes = data.to_bytes(bytes_length, byteorder="little", signed=signed)
    return data_bytes
