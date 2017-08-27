from ._ingenialink import ffi, lib
from ._utils import _pstr


def _raise(obj):
    """ Raise the corresponding exception based on the received object. """

    # constructors
    if obj == ffi.NULL:
        msg = _pstr(lib.ilerr_last())
        raise IngeniaLinkCreationError(msg)
    # return codes
    elif isinstance(obj, int):
        if obj == 0:
            return

        # obtain message and raise its matching exception
        msg = _pstr(lib.ilerr_last())

        if obj == lib.IL_EINVAL:
            raise IngeniaLinkValueError(msg)
        elif obj == lib.IL_ETIMEDOUT:
            raise IngeniaLinkTimeoutError(msg)
        elif obj == lib.IL_ENOMEM:
            raise IngeniaLinkMemoryError(msg)
        elif obj == lib.IL_EFRAME:
            raise IngeniaLinkFrameError(msg)
        elif obj == lib.IL_EFAULT:
            raise IngeniaLinkFaultError(msg)
        else:
            raise IngeniaLinkError(msg)


class IngeniaLinkError(Exception):
    """ IngeniaLink generic error. """
    pass


class IngeniaLinkCreationError(IngeniaLinkError):
    """ IngeniaLink creation error. """
    pass


class IngeniaLinkValueError(IngeniaLinkError):
    """ IngeniaLink value error. """
    pass


class IngeniaLinkTimeoutError(IngeniaLinkError):
    """ IngeniaLink timeout error. """
    pass


class IngeniaLinkMemoryError(IngeniaLinkError):
    """ IngeniaLink memory error. """
    pass


class IngeniaLinkFrameError(IngeniaLinkError):
    """ IngeniaLink frame error. """
    pass


class IngeniaLinkFaultError(IngeniaLinkError):
    """ IngeniaLink fault error. """
    pass
