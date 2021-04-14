from ._ingenialink import ffi, lib


def err_ipb_last():
    """ Get IPB last last occurred error. """
    return int(ffi.cast("int", lib.ilerr_ipb_last()))