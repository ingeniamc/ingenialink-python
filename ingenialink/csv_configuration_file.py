import binascii
import csv
from dataclasses import dataclass
from typing import Optional, cast

from ingenialink.ethercat.register import EthercatRegister
from ingenialink.table import Table
from ingenialink.utils._utils import dtype_value


@dataclass
class RegisterRow:
    """Dataclass to hold a register row for CSV writing."""

    index: str
    subindex: str
    value: str

    @classmethod
    def from_register(cls, register: EthercatRegister, storage: bytes) -> "RegisterRow":
        """Create a RegisterRow from an EthercatRegister and a storage value.

        Args:
            register: The EthercatRegister to convert.
            storage: The value to store in the register.

        Returns:
            A RegisterRow instance.

        """
        index = f"0x{register.idx:04X}"
        subindex = f"0x{register.subidx:02X}"
        value = cls.__format_value_for_csv(register, storage)
        return cls(index, subindex, value)

    def to_bytes(self) -> bytes:
        """Return the row data as UTF-8 encoded bytes for the CRC calculation."""
        return ",".join(self.csv_row).encode()

    @staticmethod
    def __format_value_for_csv(reg: EthercatRegister, value: bytes) -> str:
        """Format a value to be stored in a CSV configuration file.

        Args:
            reg: The register of the value.
            value: The value to be formatted.

        Returns:
            The formatted value.
        """
        # Trim read data to avoid reading garbage
        # To be fixed in INGK-1176
        bytes_length, _ = dtype_value[reg.dtype]
        value = value[:bytes_length]
        # Convert from little endian to big endian
        value = value[::-1]
        return f"0x{value.hex().upper()}"

    @property
    def csv_row(self) -> list[str]:
        """Return the row data as a list for CSV writing."""
        return [self.index, self.subindex, self.value]


class CSVConfigurationFile:
    """Class to generate CSV configuration files for Summit Drive.

    Only intended for EtherCAT devices.

    """

    __VERSION = "v1"

    def __init__(self, filename: str) -> None:
        """Initialize the CSVConfigurationFile.

        Args:
            filename: The name of the file to write the configuration to.

        """
        self.__filename = filename
        self.__data: list[RegisterRow] = []
        self.__crc = 0x0000

    @classmethod
    def load_from_csv(cls, filename: str) -> "CSVConfigurationFile":
        """Load a CSV configuration file.

        Args:
            filename: The path to the CSV file.

        Returns:
            A CSVConfigurationFile instance loaded from the file.

        Raises:
            ValueError: If the CSV format is invalid.
        """
        instance = cls(filename)
        with open(filename, newline="") as file:
            reader = csv.reader(file)
            rows = list(reader)
        if not rows or rows[0] != [cls.__VERSION]:
            raise ValueError("Invalid CSV format: missing or incorrect version")
        crc_str = rows[1][0]
        try:
            instance.__crc = int(crc_str, 16)
        except ValueError:
            raise ValueError(f"Invalid CRC format: {crc_str}")
        for row in rows[2:]:
            if len(row) != 3:
                raise ValueError(f"Invalid row format: {row}")
            index, subindex, value = row
            instance.__data.append(RegisterRow(index, subindex, value))
        return instance

    def add_register(self, register: EthercatRegister, storage: bytes) -> None:
        """Add a register to the CSV configuration.

        Args:
            register: The register to add.
            storage: The value to store in the register.
        """
        row = RegisterRow.from_register(register, storage)
        self.__calculate_crc(row)
        self.__data.append(row)

    def add_table(self, table: Table) -> None:
        """Add all registers from a table to the CSV configuration.

        Args:
            table: The table containing the registers to add.

        Raises:
            TypeError: If the table does not use EtherCAT registers.
        """
        index_reg = table.index_register
        value_reg = table.value_register
        if not isinstance(index_reg, EthercatRegister) or not isinstance(
            value_reg, EthercatRegister
        ):
            raise TypeError("Only EtherCAT registers are supported in CSV files.")
        for address, raw_value in table.items_raw():
            self.add_register(index_reg, index_reg.value_to_bytes(address))
            self.add_register(value_reg, raw_value)

    def write_to_file(self) -> None:
        """Generate the CSV configuration file."""
        with open(self.__filename, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([self.__VERSION])
            writer.writerow([f"0x{self.__crc:04X}"])
            for row in self.__data:
                writer.writerow(row.csv_row)

    def compare_with_table(self, table: Table) -> list[str]:
        """Compare the CSV configuration contents with a table.

        Returns:
            A list of mismatch or error messages. The list is empty when the
            CSV contents match the current table values.
        """
        mismatches: list[str] = []
        index_reg = cast("EthercatRegister", table.index_register)
        value_reg = cast("EthercatRegister", table.value_register)
        current_address: Optional[int] = None

        bytes_length, _ = dtype_value[value_reg.dtype]
        index_reg_key = f"0x{index_reg.idx:04X}", f"0x{index_reg.subidx:02X}"
        value_reg_key = f"0x{value_reg.idx:04X}", f"0x{value_reg.subidx:02X}"

        for row in self.__data:
            if (row.index, row.subindex) == index_reg_key:
                try:
                    current_address = (
                        int(row.value[2:], 16) if row.value.startswith("0x") else int(row.value, 16)
                    )
                except ValueError as exc:
                    mismatches.append(f"Invalid index value for row {row.csv_row}: {exc}")
                    current_address = None
                continue

            if (row.index, row.subindex) != value_reg_key:
                continue

            if current_address is None:
                mismatches.append("CSV value row found before an index row for the target table.")
                continue

            try:
                expected_raw = bytes.fromhex(
                    row.value[2:] if row.value.startswith("0x") else row.value
                )
            except ValueError as exc:
                mismatches.append(f"Invalid value for CSV row {row.csv_row}: {exc}")
                continue

            try:
                drive_raw = table.get_value_raw(current_address)
            except Exception as exc:
                mismatches.append(
                    f"Table {value_reg.identifier} address {current_address} -- {exc}"
                )
                continue

            actual_raw = drive_raw[:bytes_length][::-1]
            if actual_raw != expected_raw:
                mismatches.append(
                    f"Table {value_reg.identifier} address {current_address} --- "
                    f"Expected: 0x{expected_raw.hex().upper()} Found: 0x{actual_raw.hex().upper()}"
                )

        return mismatches

    def __calculate_crc(self, row: RegisterRow) -> None:
        """Calculate the CRC for a given row and update the internal CRC state.

        Args:
            row: The RegisterRow to include in the CRC calculation.

        """
        self.__crc = binascii.crc_hqx(row.to_bytes(), self.__crc)
