from ._ingenialink import ffi


def _cstr(v):
    """ Convert Python string to C compatible char *. """
    return v.encode('utf8')


def _pstr(v):
    """ Convert C string to Python compatible str. """
    return ffi.string(v).decode('utf8')
