from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, Optional

from ingenialink.configuration_file import ConfigTable, TableElement
from ingenialink.utils._utils import REG_VALUE, convert_bytes_to_dtype

if TYPE_CHECKING:
    from ingenialink import Register, Servo
    from ingenialink.dictionary import DictionaryTable


class Table:
    """Table.

    Internal table that stores N values that are accessed by index register
    and read/written via value register.
    """

    def __init__(
        self,
        servo: "Servo",
        table: "DictionaryTable",
    ) -> None:
        """Initializes the Table.

        Args:
            servo: Servo instance.
            table: Dictionary table instance.

        Raises:
            ValueError: If index register does not have integer range.
        """
        self.__servo = servo
        self.__dict_table = table

        self.__index_register = self.__servo.dictionary.get_register(
            self.__dict_table.id_index, axis=self.__dict_table.axis
        )
        self.__value_register = self.__servo.dictionary.get_register(
            self.__dict_table.id_value, axis=self.__dict_table.axis
        )

        min_index, max_index = self.__index_register.range
        if not isinstance(min_index, int) or not isinstance(max_index, int):
            raise ValueError("Index register must have integer range.")

        if min_index < 0:
            # Negative indexes may be used to not request any particular index.
            min_index = 0

        self.__min_index = min_index
        self.__max_index = max_index

    @property
    def index_register(self) -> "Register":
        """Index register used to access the table."""
        return self.__index_register

    @property
    def value_register(self) -> "Register":
        """Value register used to read/write table values."""
        return self.__value_register

    def get_value(self, index: int) -> REG_VALUE:
        """Reads a value from the table.

        Args:
            index: Index of the value to read.

        Returns:
            Value at the specified index.
        """
        self.__servo.write(self.__index_register, index)
        return self.__servo.read(self.__value_register)

    def set_value(self, index: int, value: REG_VALUE) -> None:
        """Writes a value to the table.

        Args:
            index: Index of the value to write.
            value: Value to write at the specified index.
        """
        self.__servo.write(self.__index_register, index)
        self.__servo.write(self.__value_register, value)

    def get_value_raw(self, index: int) -> bytes:
        """Reads a raw value from the table.

        Args:
            index: Index of the value to read.

        Returns:
            Raw value at the specified index
        """
        self.__servo.write(self.__index_register, index)
        return self.__servo._read_raw(self.__value_register)

    def set_value_raw(self, index: int, raw_value: bytes) -> None:
        """Writes a raw value to the table.

        Args:
            index: Index of the value to write.
            raw_value: Raw bytes to write at the specified index.
        """
        self.__servo.write(self.__index_register, index)
        self.__servo._write_raw(self.__value_register, raw_value)

    def __len__(self) -> int:
        """Returns the number of elements in the table.

        Returns:
            Number of elements in the table
        """
        return self.__max_index - self.__min_index + 1

    def __iter__(self) -> Iterator[REG_VALUE]:
        """Iterate over all values in the table.

        Yields:
            Each value in the table from min_index to max_index.
        """
        for i in range(self.__min_index, self.__max_index + 1):
            yield self.get_value(i)

    def addresses(self) -> Iterator[int]:
        """Iterate over all addresses in the table.

        Yields:
            Each address in the table from min_index to max_index.
        """
        yield from range(self.__min_index, self.__max_index + 1)

    def items(self) -> Iterator[tuple[int, REG_VALUE]]:
        """Iterate over all index-value pairs in the table.

        Yields:
            Tuples of (index, value) for each entry in the table.
        """
        for addr in self.addresses():
            yield addr, self.get_value(addr)

    def items_raw(self) -> Iterator[tuple[int, bytes]]:
        """Iterate over all index-raw_value pairs in the table.

        Yields:
            Tuples of (index, raw_value) for each entry in the table.
        """
        for addr in self.addresses():
            yield addr, self.get_value_raw(addr)

    def __getitem__(self, index: int) -> REG_VALUE:
        """Read a value from the table using bracket notation.

        Args:
            index: Index of the value to read.

        Returns:
            Value at the specified index.

        Raises:
            IndexError: If index is out of range.
        """
        if index < self.__min_index or index > self.__max_index:
            raise IndexError(f"Index {index} out of range [{self.__min_index}, {self.__max_index}]")
        return self.get_value(index)

    def __setitem__(self, index: int, value: REG_VALUE) -> None:
        """Write a value to the table using bracket notation.

        Args:
            index: Index of the value to write.
            value: Value to write at the specified index.

        Raises:
            IndexError: If index is out of range.
        """
        if index < self.__min_index or index > self.__max_index:
            raise IndexError(f"Index {index} out of range [{self.__min_index}, {self.__max_index}]")
        self.set_value(index, value)

    def read(
        self, start_index: Optional[int] = None, count: Optional[int] = None
    ) -> list[REG_VALUE]:
        """Read multiple values from the table.

        Args:
            start_index: Starting index. Defaults to min_index.
            count: Number of values to read. Defaults to all remaining.

        Returns:
            List of values read from the table.

        Raises:
            IndexError: If the range is out of bounds.
        """
        if start_index is None:
            start_index = self.__min_index

        if count is None:
            count = self.__max_index - start_index + 1

        end_index = start_index + count - 1

        if start_index < self.__min_index or end_index > self.__max_index:
            raise IndexError(
                f"Range [{start_index}, {end_index}] out of bounds "
                f"[{self.__min_index}, {self.__max_index}]"
            )

        return [self.get_value(i) for i in range(start_index, end_index + 1)]

    def write(self, values: Sequence[REG_VALUE], start_index: Optional[int] = None) -> None:
        """Write multiple values to the table.

        Args:
            values: Sequence of values to write to the table.
            start_index: Starting index. Defaults to min_index.

        Raises:
            IndexError: If the range is out of bounds.
        """
        if start_index is None:
            start_index = self.__min_index

        end_index = start_index + len(values) - 1

        if start_index < self.__min_index or end_index > self.__max_index:
            raise IndexError(
                f"Range [{start_index}, {end_index}] out of bounds "
                f"[{self.__min_index}, {self.__max_index}]"
            )

        for i, value in enumerate(values):
            self.set_value(start_index + i, value)

    def to_config_table(self) -> ConfigTable:
        """Convert to ConfigTable representation with the current table values.

        Returns:
            ConfigTable instance with the current table values.
        """
        config_table = ConfigTable(uid=self.__dict_table.id, subnode=self.__dict_table.axis or 0)
        for address, raw_value in self.items_raw():
            element = TableElement(address=address, data=raw_value)
            config_table.elements.append(element)
        return config_table

    def load_from_config_table(self, config_table: ConfigTable) -> None:
        """Load values of a config table to the current table.

        Args:
            config_table: Table configuration to load
        """
        for element in config_table.elements:
            self.set_value_raw(element.address, element.data)

    def compare_with_config_table(self, config_table: ConfigTable) -> list[str]:
        """Compare the current table values with a ConfigTable.

        Returns:
            A list of mismatch/error messages (empty when identical).
        """
        mismatches: list[str] = []
        # Use the dictionary id for messages
        uid = self.__dict_table.id
        for element in config_table.elements:
            try:
                drive_raw = self.get_value_raw(element.address)
            except Exception as e:
                mismatches.append(f"Table {uid} address {element.address} -- {e}")
                continue

            expected = convert_bytes_to_dtype(element.data, self.__value_register.dtype)
            found = convert_bytes_to_dtype(drive_raw, self.__value_register.dtype)
            if expected != found:
                mismatches.append(
                    f"Table {uid} address {element.address} --- Expected: {expected!r} "
                    f"Found: {found!r}\n"
                )
        return mismatches
