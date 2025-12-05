from typing import TYPE_CHECKING, Optional

from ingenialink.utils._utils import REG_VALUE

if TYPE_CHECKING:
    from ingenialink import Servo
    from ingenialink.dictionary import DictionaryTable


class Table:
    """Table.

    Internal table that stores N values that are accessed by index register
    and read/written via value register.
    """

    def __init__(
        self, servo: "Servo", table: "DictionaryTable", axis: Optional[int] = None
    ) -> None:
        """Initializes the Table.

        Args:
            servo (Servo): Servo instance.
            table (DictionaryTable): Dictionary table instance.
            axis (Optional[int]): Axis number for multi-axis servos

        Raises:
            ValueError: If index register does not have integer range.
        """
        self.__servo = servo
        self.__table = table

        self.__index_register = self.__servo.dictionary.get_register(
            self.__table.id_index, axis=axis
        )
        self.__value_register = self.__servo.dictionary.get_register(
            self.__table.id_value, axis=axis
        )

        min_index, max_index = self.__index_register.range
        if not isinstance(min_index, int) or not isinstance(max_index, int):
            raise ValueError("Index register must have integer range.")

        if min_index < 0:
            # Negative indexes may be used to not request any particular index.
            min_index = 0

        self.__min_index = min_index
        self.__max_index = max_index

    def get_value(self, index: int) -> REG_VALUE:
        """Reads a value from the table.

        Args:
            index (int): Index of the value to read.

        Returns:
            int: Value at the specified index.
        """
        self.__servo.write(self.__index_register, index)
        return self.__servo.read(self.__value_register)

    def set_value(self, index: int, value: REG_VALUE) -> None:
        """Writes a value to the table.

        Args:
            index (int): Index of the value to write.
            value (int): Value to write at the specified index.
        """
        self.__servo.write(self.__index_register, index)
        self.__servo.write(self.__value_register, value)
