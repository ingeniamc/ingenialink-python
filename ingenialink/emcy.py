from typing import TYPE_CHECKING, Optional, Union

try:
    import pysoem
except ImportError:
    pysoem = None
from canopen.emcy import EmcyError

if TYPE_CHECKING:
    from pysoem import Emergency

    from ingenialink import Servo


class EmergencyMessage:
    """Emergency message class.

    Args:
        servo: The servo that generated the emergency error.
        emergency_msg: The emergency message instance from PySOEM or canopen.

    """

    def __init__(self, servo: "Servo", emergency_msg: Union["Emergency", EmcyError]):
        self.servo = servo
        if isinstance(emergency_msg, pysoem.Emergency):
            self.error_code = emergency_msg.error_code
            self.register = emergency_msg.error_reg
            self.data = (
                emergency_msg.b1.to_bytes(1, "little")
                + emergency_msg.w1.to_bytes(2, "little")
                + emergency_msg.w2.to_bytes(2, "little")
            )
        elif isinstance(emergency_msg, EmcyError):
            self.error_code = emergency_msg.code
            self.register = emergency_msg.register
            self.data = emergency_msg.data
        else:
            raise NotImplementedError

    def get_desc(self) -> Optional[str]:
        """Get the error description from the servo's dictionary."""
        if (
            self.servo.dictionary.errors is None
            or self.error_code not in self.servo.dictionary.errors
        ):
            return None
        error_description = self.servo.dictionary.errors[self.error_code].description
        if error_description is None:
            return None
        return error_description

    def __str__(self) -> str:
        text = f"Error code 0x{self.error_code:04X}"
        description = self.get_desc()
        if description is not None:
            text = f"{text}, {description}"
        return text
