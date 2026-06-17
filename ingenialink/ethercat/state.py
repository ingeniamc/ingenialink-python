from enum import Enum


class SlaveState(Enum):
    """EtherCAT state enum."""

    NONE_STATE = 0
    INIT_STATE = 1
    PREOP_STATE = 2
    BOOT_STATE = 3
    SAFEOP_STATE = 4
    OP_STATE = 8
    ERROR_STATE = 16
    PREOP_ERROR_STATE = PREOP_STATE + ERROR_STATE
    SAFEOP_ERROR_STATE = SAFEOP_STATE + ERROR_STATE
