from typing import TYPE_CHECKING, Union

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

    def get_desc(self) -> str:
        """Get the error description from the servo's dictionary"""
        error_code = self.error_code & 0xFFFF
        if (
            self.servo.dictionary.errors is None
            or error_code not in self.servo.dictionary.errors.errors
        ):
            return ""
        error_description = self.servo.dictionary.errors.errors[error_code][-1]
        if error_description is None:
            return ""
        return error_description

    def __str__(self) -> str:
        text = "Error code 0x{:04X}".format(self.error_code)
        description = self.get_desc()
        if description:
            text = text + ", " + description
        return text
