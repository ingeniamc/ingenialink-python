import sys
import re

from ._ingenialink import lib
from .register_deprecated import REG_DTYPE


DIST_FRAME_SIZE_BYTES = 128
DIST_FRAME_SIZE = 512
SINGLE_AXIS_MINIMUM_SUBNODES = 2

DEFAULT_MESSAGE_RETRIES = 7
DEFAULT_MESSAGE_TIMEOUT = 200

DEFAULT_ETH_CONNECTION_TIMEOUT = 5
DEFAULT_PDS_TIMEOUT = 1000

DEFAULT_DRIVE_NAME = "Drive"

MCB_CMD_READ = 1
MCB_CMD_WRITE = 2
MCB_CMD_ACK = 3

PASSWORD_STORE_ALL = 0x65766173
PASSWORD_RESTORE_ALL = 0x64616F6C
PASSWORD_STORE_RESTORE_TCP_IP = 0x636F6D73
PASSWORD_STORE_RESTORE_SUB_0 = 0x73756230

FILE_EXT_SFU = ".sfu"
FILE_EXT_LFU = ".lfu"
FILE_EXT_SFU = '.sfu'
FILE_EXT_LFU = '.lfu'
FORCE_BOOT_PASSWORD = 0x424F4F54
FOE_WRITE_PASSWORD = 0x70636675
FORCE_COCO_BOOT_IDX = 0x5EDE
FORCE_COCO_BOOT_SUBIDX = 0x00

CAN_MONITORING_MAPPED_REGISTERS_START_ADD = 0x58D000

MONITORING_BUFFER_SIZE = 512

data_type_size = {
    REG_DTYPE.U8: 1,
    REG_DTYPE.S8: 1,
    REG_DTYPE.U16: 2,
    REG_DTYPE.S16: 2,
    REG_DTYPE.U32: 4,
    REG_DTYPE.S32: 4,
    REG_DTYPE.U64: 8,
    REG_DTYPE.S64: 8,
    REG_DTYPE.FLOAT: 4,
}

CAN_MAX_WRITE_SIZE = 512
ETH_MAX_WRITE_SIZE = 512
ETH_BUF_SIZE = 1024


def _load():
    """Load IngeniaLink constants to this module."""
    module = sys.modules[__name__]
    const_pattern = re.compile("ILK_(.*)")

    # add all constants to the module dictionary
    for k in lib.__dict__:
        m = const_pattern.match(k)
        if m:
            name = m.groups()[0]
            module.__dict__[name] = lib.__dict__[k]


_load()
