from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ingenialink import Servo


class EmergencyMessage:
    """Emergency message class.

    Args:
        servo: The servo that generated the emergency error.
        error_code: EMCY code
        register: Error register
        data: Vendor specific data
    """

    def __init__(self, servo: "Servo", error_code: int, register: int, data: bytes):
        self.servo = servo
        self.error_code = error_code
        self.register = register
        self.data = data

    def get_desc(self) -> Optional[str]:
        """Get the error description from the servo's dictionary.

        Returns:
            Error description.
        """
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
        """String representation.

        Returns:
            string representation.
        """
        text = f"Error code 0x{self.error_code:04X}"
        description = self.get_desc()
        if description is not None:
            text = f"{text}, {description}"
        return text
