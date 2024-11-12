class ILError(Exception):
    """IngeniaLink generic error."""

    pass


class ILConfigurationError(ILError):
    """IngeniaLink IPB protocol configuration error."""

    pass


class ILUDPException(Exception):
    """Ingenialink exception on UDP action."""

    pass


class ILFirmwareLoadError(ILError):
    """IngeniaLink error while loading a firmware."""

    pass


class ILValueError(ILError):
    """IngeniaLink value error."""

    pass


class ILTimeoutError(ILError):
    """IngeniaLink timeout error."""

    pass


class ILAccessError(ILError):
    """IngeniaLink access error."""

    pass


class ILStateError(ILError):
    """IngeniaLink state error."""

    pass


class ILIOError(ILError):
    """IngeniaLink I/O error."""

    pass


class ILWrongRegisterError(ILError):
    """IngeniaLink Wrong register error."""

    pass


class ILRegisterNotFoundError(ILError):
    """IngeniaLink register not found in dictionary."""

    pass


class ILWrongCRCError(ILError):
    """IngeniaLink Wrong CRC error."""

    pass


class ILNACKError(ILError):
    """IngeniaLink NACK error."""

    def __init__(self, err_code: int):
        self.error_code = err_code
        super().__init__(f"Communications error (NACK -> 0x{err_code:08X})")


class ILDictionaryParseError(ILError):
    """IngeniaLink dictionary parse error."""

    pass


class ILObjectNotExist(ILConfigurationError):
    """Object doesn't exist configuration error."""

    pass


class ILWrongWorkingCount(ILError):
    """PDOs process data working count expected and received differ."""

    pass
