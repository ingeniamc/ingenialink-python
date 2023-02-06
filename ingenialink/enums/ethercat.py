from enum import Enum


class EC_STATE(Enum):
    NONE = 0x00
    INIT = 0x01
    PRE_OP = 0x02
    BOOT = 0x03
    SAFE_OP = 0x04
    OPERATIONAL = 0x08
    ERROR = 0x10
