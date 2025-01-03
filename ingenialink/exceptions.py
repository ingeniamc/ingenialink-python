class ILError(Exception):
    """IngeniaLink generic error."""



class ILConfigurationError(ILError):
    """IngeniaLink configuration error."""



class ILUDPException(ILError):
    """Ingenialink exception on UDP action."""



class ILFirmwareLoadError(ILError):
    """IngeniaLink error while loading a firmware."""



class ILValueError(ILError):
    """IngeniaLink value error."""



class ILTimeoutError(ILError):
    """IngeniaLink timeout error."""



class ILAccessError(ILError):
    """IngeniaLink access error."""



class ILStateError(ILError):
    """IngeniaLink state error."""



class ILIOError(ILError):
    """IngeniaLink I/O error."""



class ILWrongRegisterError(ILError):
    """IngeniaLink Wrong register error."""



class ILRegisterNotFoundError(ILError):
    """IngeniaLink register not found in dictionary."""



class ILWrongCRCError(ILError):
    """IngeniaLink Wrong CRC error."""



class ILNACKError(ILError):
    """IngeniaLink NACK error."""

    def __init__(self, err_code: int):
        self.error_code = err_code
        super().__init__(f"Communications error (NACK -> 0x{err_code:08X})")


class ILDictionaryParseError(ILError):
    """IngeniaLink dictionary parse error."""



class ILWrongWorkingCount(ILError):
    """PDOs process data working count expected and received differ."""

