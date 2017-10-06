import sys
import re

from ._ingenialink import lib
from . import Register


def _load():
    """ Load IngeniaLink pre-defined registers to this module. """

    module = sys.modules[__name__]
    reg_pattern = re.compile('IL_REG_(?!DTYPE|ACCESS|PHY)(.*)')

    # add all registers to the module dictionary
    for k in lib.__dict__:
        m = reg_pattern.match(k)
        if m:
            name = m.groups()[0]
            module.__dict__[name] = Register._from_register(lib.__dict__[k])


_load()
