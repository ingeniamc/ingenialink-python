from ._ingenialink import ffi, lib


def err_ipb_last():
    return int(ffi.cast("int", lib.ilerr_ipb_last()))