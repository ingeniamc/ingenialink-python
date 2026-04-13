import binascii
import csv
from dataclasses import dataclass
from typing import Optional, cast

from ingenialink import table
from ingenialink.configuration_file import ConfigTable, TableElement
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

    def extract_config_table(self, table: Table) -> ConfigTable:
        """Extract a table encoded in the CSV write sequence and return it as a ConfigTable.

        The method scans the CSV rows looking for index-register and value-register
        writes corresponding to the given table. Each index/value pair is converted
        into a TableElement using raw bytes as stored in the CSV.

        Args:
            table: Target Table definition (index/value registers are used as keys).

        Returns:
            ConfigTable populated with the extracted table elements.

        Raises:
            ValueError: If malformed rows are encountered.
        """
        index_reg = cast("EthercatRegister", table.index_register)
        value_reg = cast("EthercatRegister", table.value_register)

        index_key = (f"0x{index_reg.idx:04X}", f"0x{index_reg.subidx:02X}")
        value_key = (f"0x{value_reg.idx:04X}", f"0x{value_reg.subidx:02X}")

        # ConfigTable identifies the table logically (dictionary id + axis)
        config_table = ConfigTable(
            uid=table._Table__dict_table.id,  # same identifier used elsewhere
            subnode=table._Table__dict_table.axis or 0,
        )

        current_address: Optional[int] = None
        bytes_length, _ = dtype_value[value_reg.dtype]

        for row in self.__data:
            # --- Index register write ---
            if (row.index, row.subindex) == index_key:
                try:
                    value_str = row.value[2:] if row.value.startswith("0x") else row.value
                    current_address = int(value_str, 16)
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid index value in CSV row {row.csv_row}: {exc}"
                    ) from exc
                continue
            # --- Value register write ---
            if (row.index, row.subindex) != value_key:
                continue

            if current_address is None:
                raise ValueError(
                    "Value register row found before index register row while "
                    "extracting table from CSV."
                )

            try:
                value_str = row.value[2:] if row.value.startswith("0x") else row.value
                raw_be = bytes.fromhex(value_str)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid value data in CSV row {row.csv_row}: {exc}"
                ) from exc

            # CSV stores big-endian hex; table expects raw little-endian bytes
            raw_le = raw_be[:bytes_length][::-1]

            element = TableElement(address=current_address, data=raw_le)
            config_table.elements.append(element)

            current_address = None  # enforce index/value pairing

        return config_table

    def __calculate_crc(self, row: RegisterRow) -> None:
        """Calculate the CRC for a given row and update the internal CRC state.

        Args:
            row: The RegisterRow to include in the CRC calculation.

        """
        self.__crc = binascii.crc_hqx(row.to_bytes(), self.__crc)
