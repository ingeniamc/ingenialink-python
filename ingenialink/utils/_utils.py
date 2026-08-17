import functools
import logging
import warnings
import weakref
from typing import Any, Callable, Optional, TypeVar, Union, cast
from xml.etree import ElementTree

import ingenialogger

from ingenialink._rust import data_type as _rust_data_type
from ingenialink.enums.register import ByteOrder, RegDtype

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
    RegDtype.BOOL: 8,
    RegDtype.BYTE_ARRAY_512: 512 * 8,
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


_T = TypeVar("_T")


def weak_lru(
    maxsize: int = 128, typed: bool = False
) -> Callable[[Callable[..., _T]], Callable[..., _T]]:
    """Decorator that allows safe use of lru_cache in class methods.

    Args:
        maxsize: maximum size. Defaults to 128.
        typed: typed. Defaults to False.

    Returns:
        wrapped method.
    """

    def decorator(func: Callable[..., _T]) -> Callable[..., _T]:
        ref = weakref.ref

        @functools.lru_cache(maxsize, typed)
        def _func(_self: Any, /, *args: Any, **kwargs: Any) -> _T:
            return func(_self(), *args, **kwargs)

        @functools.wraps(func)
        def wrapper(self: Any, /, *args: Any, **kwargs: Any) -> _T:
            return _func(ref(self), *args, **kwargs)

        return cast("Callable[..., _T]", wrapper)

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


REG_VALUE = Union[float, int, str, bytes]


@functools.cache
def get_configured_codec(
    dtype: RegDtype, byte_order: ByteOrder
) -> _rust_data_type.ConfiguredDataType:
    """Return the cached native codec for a data type and byte order.

    Args:
        dtype: Register data type to convert.
        byte_order: Byte order used by the register protocol.

    Returns:
        A Rust-backed codec configured for the requested data type and byte order.

    Raises:
        RuntimeError: If the installed native extension lacks a built-in register data type.
    """
    rust_data_type = _rust_data_type.DataType.from_name(dtype.name)
    if rust_data_type is None:
        raise RuntimeError(f"Native codec does not support register data type {dtype.name}")
    return rust_data_type.with_byte_order(byte_order.value)


@deprecated(new_func_name="Register.bytes_to_value")
def convert_bytes_to_dtype(
    data: bytes, dtype: RegDtype, byte_order: ByteOrder = ByteOrder.LITTLE
) -> REG_VALUE:
    """Convert data in bytes to corresponding dtype.

    Bytes have to be ordered in LSB.

    Args:
        data: data to convert
        dtype: output dtype
        byte_order: byte order of the data

    Returns:
        Value formatted in data type

    Raises:
        ILValueError: If data can't be decoded in utf-8

    Notes:
        Fixed-width payloads may contain trailing transport padding. Such
        padding is removed before strict native decoding; short payloads are
        still rejected.
    """
    codec = get_configured_codec(dtype, byte_order)
    payload = bytes(data)
    if dtype != RegDtype.BYTE_ARRAY_512 and (byte_length := codec.byte_length()) is not None:
        payload = payload[:byte_length]
    return codec.bytes_to_value(payload)


@deprecated(new_func_name="Register.value_to_bytes")
def convert_dtype_to_bytes(
    data: REG_VALUE, dtype: RegDtype, byte_order: ByteOrder = ByteOrder.LITTLE
) -> bytes:
    """Convert data in dtype to bytes.

    Bytes will be ordered in LSB.

    Args:
        data: Data to convert.
        dtype: Data type.
        byte_order: byte order of the data

    Returns:
        Value formatted to bytes

    Raises:
        ValueError: if the data has an invalid value.
    """
    return get_configured_codec(dtype, byte_order).value_to_bytes(data)
