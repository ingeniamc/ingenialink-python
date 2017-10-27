import sys
import re

from ._ingenialink import lib


def _load():
    """ Load IngeniaLink constants to this module. """

    module = sys.modules[__name__]
    const_pattern = re.compile('ILK_(.*)')

    # add all constants to the module dictionary
    for k in lib.__dict__:
        m = const_pattern.match(k)
        if m:
            name = m.groups()[0]
            module.__dict__[name] = lib.__dict__[k]


_load()
