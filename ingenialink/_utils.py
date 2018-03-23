from enum import Enum

from ._ingenialink import lib, ffi
from . import exceptions as exc


def cstr(v):
    """ Convert Python 3.x string to C compatible char *. """

    return v.encode('utf8')


def pstr(v):
    """ Convert C string to Python 3.x compatible str. """

    return ffi.string(v).decode('utf8')


def to_ms(s):
    """ Convert from seconds to milliseconds.

        Args:
            s (float, int): Value in seconds.

        Returns:
            int: Value in milliseconds.
    """

    return int(s * 1e3)


class INT_SIZES(Enum):
    """ Integer sizes. """

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


def raise_null(obj):
    """ Raise exception if object is ffi.NULL.

        Raises:
            ILCreationError: If the object is NULL.
    """

    if obj == ffi.NULL:
        msg = pstr(lib.ilerr_last())
        raise exc.ILCreationError(msg)


def raise_err(code):
    """ Raise exception if the code is non-zero.

        Raises:
            ILValueError: if code is lib.IL_EINVAL
            ILTimeoutError: if code is lib.IL_ETIMEDOUT
            ILAlreadyInitializedError: if code is lib.IL_EALREADY
            ILMemoryError: if code is lib.IL_ENOMEM
            ILDisconnectionError: if code is lib.IL_EDISCONN
            ILAccessError: if code is lib.IL_EACCESS
            ILStateError: if code is lib.IL_ESTATE
            ILError: if code is lib.IL_EFAULT
    """

    if code == 0:
        return

    # obtain message and raise its matching exception
    msg = pstr(lib.ilerr_last())

    if code == lib.IL_EINVAL:
        raise exc.ILValueError(msg)
    elif code == lib.IL_ETIMEDOUT:
        raise exc.ILTimeoutError(msg)
    elif code == lib.IL_EALREADY:
        raise exc.ILAlreadyInitializedError(msg)
    elif code == lib.IL_ENOMEM:
        raise exc.ILMemoryError(msg)
    elif code == lib.IL_EDISCONN:
        raise exc.ILDisconnectionError(msg)
    elif code == lib.IL_EACCESS:
        raise exc.ILAccessError(msg)
    elif code == lib.IL_ESTATE:
        raise exc.ILStateError(msg)
    elif code == lib.IL_EIO:
        raise exc.ILIOError(msg)
    else:
        raise exc.ILError(msg)
