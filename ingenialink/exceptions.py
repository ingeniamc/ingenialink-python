from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ingenialink.register import Register


class ILError(Exception):
    """IngeniaLink generic error."""


class ILConfigurationError(ILError):
    """IngeniaLink configuration error."""


class ILUDPError(ILError):
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


class ILRegisterAccessError(ILIOError):
    """IngeniaLink register access error raised when a register read or write is aborted.

    Attributes:
        reg: The register that was being accessed when the failure occurred.
        base_exception: The underlying exception that caused the failure.
        reason: A message describing the specific reason for the failure.
    """

    def __init__(
        self, *, base_message: str, reg: "Register", base_exception: Exception, reason: str
    ):
        self.base_message = base_message
        self.reg = reg
        self.base_exception = base_exception
        self.reason = reason
        super().__init__(f"{base_message}. {reason}")


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


class ILConfigurationFileParseError(ILError):
    """IngeniaLink configuration file parse error."""


class ILWrongWorkingCountError(ILError):
    """PDOs process data working count expected and received differ."""


class ILEcatStateError(ILError):
    """IngeniaLink Ethercat state error."""
