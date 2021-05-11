from enum import Enum

from ._ingenialink import lib, ffi
from . import exceptions as exc
from .err import *


def cstr(v):
    """
    Convert Python 3.x string to C compatible char *.
    """
    return v.encode('utf8')


def pstr(v):
    """
    Convert C string to Python 3.x compatible str.
    """
    convert = ""
    try:
        convert = ffi.string(v).decode('utf8')
    except Exception as e:
        print("Error converting C string to Python. Exception: {}".format(e))
    return convert


def to_ms(s):
    """
    Convert from seconds to milliseconds.

    Args:
        s (float, int): Value in seconds.

    Returns:
        int: Value in milliseconds.
    """
    return int(s * 1e3)


class INT_SIZES(Enum):
    """
    Integer sizes.
    """
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
    """
    Raise exception if object is ffi.NULL.

    Raises:
        ILCreationError: If the object is NULL.
    """
    if obj == ffi.NULL:
        msg = pstr(lib.ilerr_last())
        raise exc.ILCreationError(msg)


def raise_err(code, msg=None):
    """
    Raise exception if the code is non-zero.

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
    if not msg:
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
    elif code == lib.IL_ENOTSUP:
        raise exc.ILNotSupportedError(msg)
    elif code == lib.IL_EWRONGREG:
        raise exc.ILWrongRegisterError(msg)
    elif code == lib.IL_REGNOTFOUND:
        raise exc.ILRegisterNotFoundError(msg)
    elif code == lib.IL_EWRONGCRC:
        raise exc.ILWrongCRCError(msg)
    elif code == lib.IL_ENACK:
        last_err = err_ipb_last()
        if last_err == CONFIGURATION_ERRORS.INCORRECT_ACCESS_TYPE:
            raise exc.ILIncorrectAccessType
        elif last_err == CONFIGURATION_ERRORS.OBJECT_NOT_EXIST:
            raise exc.ILObjectNotExist
        elif last_err == CONFIGURATION_ERRORS.OBJECT_NOT_CYCLIC_MAPPABLE:
            raise exc.ILObjectNotCyclicMappable
        elif last_err == CONFIGURATION_ERRORS.CYCLIC_MAPPING_TOO_LARGE:
            raise exc.ILCyclicMappingTooLarge
        elif last_err == CONFIGURATION_ERRORS.WRONG_CYCLIC_KEY:
            raise exc.ILWrongCyclicKey
        elif last_err == CONFIGURATION_ERRORS.WRONG_CYCLIC_REGISTER_SIZE:
            raise exc.ILWrongCyclicRegisterSize
        elif last_err == CONFIGURATION_ERRORS.COMMUNICATION_STATE_UNREACHABLE:
            raise exc.ILCommunicationStateUnreachable
        elif last_err == CONFIGURATION_ERRORS.COMMUNICATION_NOT_MODIFIABLE:
            raise exc.ILCommunicationNotModifiable
        elif last_err == CONFIGURATION_ERRORS.UNSUPPORTED_REGISTER_VALUE:
            raise exc.ILUnsupportedRegisterValue
        elif last_err == CONFIGURATION_ERRORS.INVALID_COMMAND:
            raise exc.ILInvalidCommand
        elif last_err == CONFIGURATION_ERRORS.CRC_ERROR:
            raise exc.ILCRCError
        elif last_err == CONFIGURATION_ERRORS.UNSUPPORTED_SYNCHRONIZATION:
            raise exc.ILUnsupportedSynchronization
        elif last_err == CONFIGURATION_ERRORS.ACTIVE_FEEDBACKS_HIGHER_THAN_ALLOWED:
            raise exc.ILActiveFeedbacksHigherThanAllowed
        elif last_err == CONFIGURATION_ERRORS.COMKIT_TIMEOUT:
            raise exc.ILCOMKITTimeout
        else:
            raise exc.ILNACKError(msg)
    else:
        raise exc.ILError(msg)
