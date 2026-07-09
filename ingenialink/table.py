from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from types import TracebackType
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

    The table contains the servo, dictionary table and the index and value registers.
    For mutable operations on the table, a context manager is used to ensure that the index register
    is restored after the operation.
    When doing multiple operations in a sequence, it is recommended to use a single context manager
    to avoid repeatedly setting the index register.
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

    @contextmanager
    def context(self) -> Iterator["TableContext"]:
        """Context manager to rollback index register after operations.

        Yields:
            TableContext instance for performing operations on the table.
        """
        with TableContext(self) as ctx:
            yield ctx

    @property
    def servo(self) -> "Servo":
        """Servo instance associated with the table."""
        return self.__servo

    @property
    def index_register(self) -> "Register":
        """Index register used to access the table."""
        return self.__index_register

    @property
    def value_register(self) -> "Register":
        """Value register used to read/write table values."""
        return self.__value_register

    @property
    def uid(self) -> str:
        """Unique identifier for the table."""
        return self.__dict_table.id

    @property
    def axis(self) -> int:
        """Axis to which the table belongs."""
        return self.__dict_table.axis or 0

    @property
    def min_index(self) -> int:
        """Minimum valid table index."""
        return self.__min_index

    @property
    def max_index(self) -> int:
        """Maximum valid table index."""
        return self.__max_index

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

    # Mutable operations delegated to a context manager

    def get_value(self, index: int) -> REG_VALUE:
        """Reads a value from the table.

        Args:
            index: Index of the value to read.

        Returns:
            Value at the specified index.
        """
        with self.context() as ctx:
            return ctx.get_value(index)

    def set_value(self, index: int, value: REG_VALUE) -> None:
        """Writes a value to the table.

        Args:
            index: Index of the value to write.
            value: Value to write at the specified index.
        """
        with self.context() as ctx:
            ctx.set_value(index, value)

    def get_value_raw(self, index: int) -> bytes:
        """Reads a raw value from the table.

        Args:
            index: Index of the value to read.

        Returns:
            Raw value at the specified index
        """
        with self.context() as ctx:
            return ctx.get_value_raw(index)

    def set_value_raw(self, index: int, raw_value: bytes) -> None:
        """Writes a raw value to the table.

        Args:
            index: Index of the value to write.
            raw_value: Raw bytes to write at the specified index.
        """
        with self.context() as ctx:
            ctx.set_value_raw(index, raw_value)

    def items(self) -> Iterator[tuple[int, REG_VALUE]]:
        """Iterate over all index-value pairs in the table.

        Yields:
            Tuples of (index, value) for each entry in the table.
        """
        with self.context() as ctx:
            yield from ctx.items()

    def items_raw(self) -> Iterator[tuple[int, bytes]]:
        """Iterate over all index-raw_value pairs in the table.

        Yields:
            Tuples of (index, raw_value) for each entry in the table.
        """
        with self.context() as ctx:
            yield from ctx.items_raw()

    def __getitem__(self, index: int) -> REG_VALUE:
        """Read a value from the table using bracket notation.

        Args:
            index: Index of the value to read.

        Returns:
            Value at the specified index.

        Raises:
            IndexError: If index is out of range.
        """
        with self.context() as ctx:
            return ctx.__getitem__(index)  # This will raise IndexError if out of range

    def __setitem__(self, index: int, value: REG_VALUE) -> None:
        """Write a value to the table using bracket notation.

        Args:
            index: Index of the value to write.
            value: Value to write at the specified index.

        Raises:
            IndexError: If index is out of range.
        """
        with self.context() as ctx:
            ctx.__setitem__(index, value)

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
        with self.context() as ctx:
            return ctx.read(start_index=start_index, count=count)

    def write(self, values: Sequence[REG_VALUE], start_index: Optional[int] = None) -> None:
        """Write multiple values to the table.

        Args:
            values: Sequence of values to write to the table.
            start_index: Starting index. Defaults to min_index.

        Raises:
            IndexError: If the range is out of bounds.
        """
        with self.context() as ctx:
            ctx.write(values, start_index=start_index)

    def to_config_table(self) -> ConfigTable:
        """Convert to ConfigTable representation with the current table values.

        Returns:
            ConfigTable instance with the current table values.
        """
        with self.context() as ctx:
            return ctx.to_config_table()

    def load_from_config_table(self, config_table: ConfigTable) -> None:
        """Load values of a config table to the current table.

        Args:
            config_table: Table configuration to load
        """
        with self.context() as ctx:
            ctx.load_from_config_table(config_table)

    def compare_with_config_table(self, config_table: ConfigTable) -> list[str]:
        """Compare the current table values with a ConfigTable.

        Returns:
            A list of mismatch/error messages (empty when identical).
        """
        with self.context() as ctx:
            return ctx.compare_with_config_table(config_table)


class TableContext:
    """Context manager to rollback index register after operations."""

    def __init__(self, table: "Table") -> None:
        """Initialize the TableContext with the given table.

        Args:
            table: Table instance to manage within the context.
        """
        self._table = table
        self._original_index: Optional[REG_VALUE] = None

    def __enter__(self) -> "TableContext":
        """Store the original index register value when entering the context.

        Returns:
            The TableContext instance itself for use within the context.
        """
        self._original_index = self._table.servo.read(self._table.index_register)
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """Restore the original index register value when exiting the context.

        Raises:
            ValueError: If the original index is None when exiting the context.
        """
        if self._original_index is None:
            raise ValueError("Original index should not be None when exiting the context.")
        self._table.servo.write(self._table.index_register, self._original_index)

    def get_value(self, index: int) -> REG_VALUE:
        """Read a value from the table within the context.

        Args:
            index: Index of the value to read.

        Returns:
            Value at the specified index.
        """
        self._table.servo.write(self._table.index_register, index)
        return self._table.servo.read(self._table.value_register)

    def set_value(self, index: int, value: REG_VALUE) -> None:
        """Write a value to the table within the context.

        Args:
            index: Index of the value to write.
            value: Value to write at the specified index.
        """
        self._table.servo.write(self._table.index_register, index)
        self._table.servo.write(self._table.value_register, value)

    def get_value_raw(self, index: int) -> bytes:
        """Read a raw value from the table within the context.

        Args:
            index: Index of the value to read.

        Returns:
            Raw value at the specified index
        """
        self._table.servo.write(self._table.index_register, index)
        return self._table.servo._read_raw(self._table.value_register)

    def set_value_raw(self, index: int, raw_value: bytes) -> None:
        """Write a raw value to the table within the context.

        Args:
            index: Index of the value to write.
            raw_value: Raw bytes to write at the specified index.
        """
        self._table.servo.write(self._table.index_register, index)
        self._table.servo._write_raw(self._table.value_register, raw_value)

    def __iter__(self) -> Iterator[REG_VALUE]:
        """Iterate over all values in the table within the context.

        Yields:
            Each value in the table from min_index to max_index.
        """
        for i in range(self._table.min_index, self._table.max_index + 1):
            yield self.get_value(i)

    def __getitem__(self, index: int) -> REG_VALUE:
        """Read a value from the table using bracket notation.

        Args:
            index: Index of the value to read.

        Returns:
            Value at the specified index.

        Raises:
            IndexError: If index is out of range.
        """
        if index < self._table.min_index or index > self._table.max_index:
            raise IndexError(
                f"Index {index} out of range [{self._table.min_index}, {self._table.max_index}]"
            )
        return self.get_value(index)

    def __setitem__(self, index: int, value: REG_VALUE) -> None:
        """Write a value to the table using bracket notation.

        Args:
            index: Index of the value to write.
            value: Value to write at the specified index.

        Raises:
            IndexError: If index is out of range.
        """
        if index < self._table.min_index or index > self._table.max_index:
            raise IndexError(
                f"Index {index} out of range [{self._table.min_index}, {self._table.max_index}]"
            )
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
            start_index = self._table.min_index

        if count is None:
            count = self._table.max_index - start_index + 1

        end_index = start_index + count - 1

        if start_index < self._table.min_index or end_index > self._table.max_index:
            raise IndexError(
                f"Range [{start_index}, {end_index}] out of bounds "
                f"[{self._table.min_index}, {self._table.max_index}]"
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
            start_index = self._table.min_index

        end_index = start_index + len(values) - 1

        if start_index < self._table.min_index or end_index > self._table.max_index:
            raise IndexError(
                f"Range [{start_index}, {end_index}] out of bounds "
                f"[{self._table.min_index}, {self._table.max_index}]"
            )

        for i, value in enumerate(values):
            self.set_value(start_index + i, value)

    def to_config_table(self) -> ConfigTable:
        """Convert to ConfigTable representation with the current table values.

        Returns:
            ConfigTable instance with the current table values.
        """
        config_table = ConfigTable(uid=self._table.uid, subnode=self._table.axis or 0)
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
        uid = self._table.uid
        for element in config_table.elements:
            try:
                drive_raw = self.get_value_raw(element.address)
            except Exception as e:
                mismatches.append(f"Table {uid} address {element.address} -- {e}")
                continue

            expected = convert_bytes_to_dtype(element.data, self.value_register.dtype)
            found = convert_bytes_to_dtype(drive_raw, self.value_register.dtype)
            if expected != found:
                mismatches.append(
                    f"Table {uid} address {element.address} --- Expected: {expected!r} "
                    f"Found: {found!r}\n"
                )
        return mismatches

    # Read only quick access properties for the underlying table and registers

    @property
    def index_register(self) -> "Register":
        """Index register used to access the table."""
        return self._table.index_register

    @property
    def value_register(self) -> "Register":
        """Value register used to read/write table values."""
        return self._table.value_register

    @property
    def uid(self) -> str:
        """Unique identifier for the table."""
        return self._table.uid

    @property
    def axis(self) -> int:
        """Axis to which the table belongs."""
        return self._table.axis

    def __len__(self) -> int:
        """Returns the number of elements in the table.

        Returns:
            Number of elements in the table
        """
        return len(self._table)

    def addresses(self) -> Iterator[int]:
        """Iterate over all addresses in the table within the context.

        Yields:
            Each address in the table from min_index to max_index.
        """
        yield from self._table.addresses()

    def items(self) -> Iterator[tuple[int, REG_VALUE]]:
        """Iterate over all index-value pairs in the table within the context.

        Yields:
            Tuples of (index, value) for each entry in the table.
        """
        for address in self.addresses():
            yield address, self.get_value(address)

    def items_raw(self) -> Iterator[tuple[int, bytes]]:
        """Iterate over all index-raw_value pairs in the table within the context.

        Yields:
            Tuples of (index, raw_value) for each entry in the table.
        """
        for address in self.addresses():
            yield address, self.get_value_raw(address)

    @property
    def min_index(self) -> int:
        """Minimum valid table index."""
        return self._table.min_index

    @property
    def max_index(self) -> int:
        """Maximum valid table index."""
        return self._table.max_index
