from enum import Enum

from ._ingenialink import lib, ffi
from . import exceptions as exc
from .err import *

import warnings
import functools


def deprecated(custom_msg=None, new_func_name=None):
    """ This is a decorator which can be used to mark functions as deprecated. It will
    result in a warning being emitted when the function is used. We use this decorator instead
    of any deprecation library because all libraries raise a DeprecationWarning but since by
    default this warning is hidden, we use this decorator to manually activate DeprecationWarning
    and turning it off after the warn has been done. """
    def wrap(func):
        @functools.wraps(func)
        def wrapped_method(*args, **kwargs):
            warnings.simplefilter('always', DeprecationWarning)  # Turn off filter
            msg = 'Call to deprecated function "{}".'.format(func.__name__)
            if new_func_name:
                msg += ' Please, use "{}" function instead.'.format(new_func_name)
            if custom_msg:
                msg = custom_msg
            warnings.warn(msg, category=DeprecationWarning, stacklevel=2)
            warnings.simplefilter('ignore', DeprecationWarning)  # Reset filter
            return func(*args, **kwargs)

        return wrapped_method

    return wrap


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


def remove_xml_subelement(element, subelement):
    """
    Removes a subelement from the given element the element contains the subelement

    Args:
        element (Element): Element to be extracted from.
        subelement (Element): Element to be extracted.
    """
    if subelement is not None and subelement in element:
        element.remove(subelement)


def pop_element(dictionary, element):
    """
    Pops an element from a dictionary only if it is contained in it

    Args:
        dictionary (dict): Dictionary containing all the elment.s
        element (str): Element to be poped from the dictionary.
    """
    if element in dictionary:
        dictionary.pop(element)


def cleanup_register(register):
    """
    Cleans a ElementTree register to remove all unnecessary fields for a configuration file

    Args:
        register (Register): Register to be cleaned.
    """
    labels = register.find('./Labels')
    range = register.find('./Range')
    enums = register.find('./Enumerations')

    remove_xml_subelement(register, labels)
    remove_xml_subelement(register, enums)
    remove_xml_subelement(register, range)

    pop_element(register.attrib, 'desc')
    pop_element(register.attrib, 'cat_id')
    pop_element(register.attrib, 'cyclic')
    pop_element(register.attrib, 'units')
    pop_element(register.attrib, 'address_type')

    register.text = ''


def get_drive_identification(servo, subnode=0):
    """
    Gets the identification information of a given subnode.

    Args:
        servo: Instance of the servo Class.
        subnode: subnode to be targeted.

    Returns:
        int, int: Product code and revision number of the targeted subnode.
    """
    prod_code = None
    re_number = None
    try:
        if subnode == 0:
            prod_code = servo.read('DRV_ID_PRODUCT_CODE_COCO', subnode)
            re_number = servo.read('DRV_ID_REVISION_NUMBER_COCO', subnode)
        else:
            prod_code = servo.read('DRV_ID_PRODUCT_CODE', subnode=subnode)
            re_number = servo.read('DRV_ID_REVISION_NUMBER', subnode)
    except Exception as e:
        pass

    return prod_code, re_number


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
            raise exc.ILIncorrectAccessType(msg)
        elif last_err == CONFIGURATION_ERRORS.OBJECT_NOT_EXIST:
            raise exc.ILObjectNotExist(msg)
        elif last_err == CONFIGURATION_ERRORS.OBJECT_NOT_CYCLIC_MAPPABLE:
            raise exc.ILObjectNotCyclicMappable(msg)
        elif last_err == CONFIGURATION_ERRORS.CYCLIC_MAPPING_TOO_LARGE:
            raise exc.ILCyclicMappingTooLarge(msg)
        elif last_err == CONFIGURATION_ERRORS.WRONG_CYCLIC_KEY:
            raise exc.ILWrongCyclicKey(msg)
        elif last_err == CONFIGURATION_ERRORS.WRONG_CYCLIC_REGISTER_SIZE:
            raise exc.ILWrongCyclicRegisterSize(msg)
        elif last_err == CONFIGURATION_ERRORS.COMMUNICATION_STATE_UNREACHABLE:
            raise exc.ILCommunicationStateUnreachable(msg)
        elif last_err == CONFIGURATION_ERRORS.COMMUNICATION_NOT_MODIFIABLE:
            raise exc.ILCommunicationNotModifiable(msg)
        elif last_err == CONFIGURATION_ERRORS.UNSUPPORTED_REGISTER_VALUE:
            raise exc.ILUnsupportedRegisterValue(msg)
        elif last_err == CONFIGURATION_ERRORS.INVALID_COMMAND:
            raise exc.ILInvalidCommand(msg)
        elif last_err == CONFIGURATION_ERRORS.CRC_ERROR:
            raise exc.ILCRCError(msg)
        elif last_err == CONFIGURATION_ERRORS.UNSUPPORTED_SYNCHRONIZATION:
            raise exc.ILUnsupportedSynchronization(msg)
        elif last_err == CONFIGURATION_ERRORS.ACTIVE_FEEDBACKS_HIGHER_THAN_ALLOWED:
            raise exc.ILActiveFeedbacksHigherThanAllowed(msg)
        elif last_err == CONFIGURATION_ERRORS.COMKIT_TIMEOUT:
            raise exc.ILCOMKITTimeout(msg)
        else:
            raise exc.ILNACKError(msg)
    else:
        raise exc.ILError(msg)
