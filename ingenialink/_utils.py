import sys
from ._ingenialink import ffi


if sys.version_info >= (3, 0):
    def _cstr(v):
        """ Convert Python 3.x string to C compatible char *. """
        return v.encode('utf8')

    def _pstr(v):
        """ Convert C string to Python 3.x compatible str. """
        return ffi.string(v).decode('utf8')
else:
    def _cstr(v):
        """ Convert Python 2.x string to C compatible char *. """
        return v

    def _pstr(v):
        """ Convert C string to Python 2.x compatible str. """
        return ffi.string(v)
