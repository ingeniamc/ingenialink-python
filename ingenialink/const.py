import sys
import re
from ingenialink.registers import Register, REG_ACCESS, REG_DTYPE

from ._ingenialink import lib


DIST_FRAME_SIZE_BYTES = 128
DIST_FRAME_SIZE = 512
SINGLE_AXIS_MINIMUM_SUBNODES = 2

DEFAULT_DRIVE_NAME = 'Drive'

# ETHERNET & ETHERCAT
PASSWORD_STORE_ALL = 0x65766173
PASSWORD_RESTORE_ALL = 0x64616F6C

DIST_NUMBER_SAMPLES = Register(
    identifier='', units='', subnode=0, address=0x00C4, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RW, range=None
)
DIST_DATA = Register(
    identifier='', units='', subnode=0, address=0x00B4, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.WO, range=None
)

STORE_COCO_ALL = Register(
    identifier='', units='', subnode=0, address=0x06DB, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RW, range=None
)

RESTORE_COCO_ALL = Register(
    identifier='', units='', subnode=0, address=0x06DC, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RW, range=None
)

STORE_MOCO_ALL_REGISTERS = {
    1: Register(
        identifier='', units='', subnode=1, address=0x06DB, cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RW, range=None
    ),
    2: Register(
        identifier='', units='', subnode=2, address=0x06DB, cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RW, range=None
    ),
    3: Register(
        identifier='', units='', subnode=3, address=0x06DB, cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RW, range=None
    )
}


def _load():
    """Load IngeniaLink constants to this module."""
    module = sys.modules[__name__]
    const_pattern = re.compile('ILK_(.*)')

    # add all constants to the module dictionary
    for k in lib.__dict__:
        m = const_pattern.match(k)
        if m:
            name = m.groups()[0]
            module.__dict__[name] = lib.__dict__[k]


_load()
