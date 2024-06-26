from enum import IntEnum


class CONFIGURATION_ERRORS(IntEnum):
    """Configuration errors."""

    INCORRECT_ACCESS_TYPE = 0x06010000
    OBJECT_NOT_EXIST = 0x06020000
    OBJECT_NOT_CYCLIC_MAPPABLE = 0x06040041
    CYCLIC_MAPPING_TOO_LARGE = 0x06040042
    WRONG_CYCLIC_KEY = 0x08010000
    WRONG_CYCLIC_REGISTER_SIZE = 0x06070010
    COMMUNICATION_STATE_UNREACHABLE = 0x08010010
    COMMUNICATION_NOT_MODIFIABLE = 0x08010020
    UNSUPPORTED_REGISTER_VALUE = 0x060A0000
    INVALID_COMMAND = 0x08010030
    CRC_ERROR = 0x08010040
    UNSUPPORTED_SYNCHRONIZATION = 0x00007400
    ACTIVE_FEEDBACKS_HIGHER_THAN_ALLOWED = 0x00007500
    COMKIT_TIMEOUT = 0x05040000
