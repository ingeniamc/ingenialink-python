import binascii
import csv
from dataclasses import dataclass

from ingenialink.ethercat.register import EthercatRegister
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

    def add_register(self, register: EthercatRegister, storage: bytes) -> None:
        """Add a register to the CSV configuration.

        Args:
            register: The register to add.
            storage: The value to store in the register.
        """
        row = RegisterRow.from_register(register, storage)
        self.__calculate_crc(row)
        self.__data.append(row)

    def write_to_file(self) -> None:
        """Generate the CSV configuration file."""
        with open(self.__filename, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([self.__VERSION])
            writer.writerow([f"0x{self.__crc:04X}"])
            for row in self.__data:
                writer.writerow(row.csv_row)

    def __calculate_crc(self, row: RegisterRow) -> None:
        """Calculate the CRC for a given row and update the internal CRC state.

        Args:
            row: The RegisterRow to include in the CRC calculation.

        """
        self.__crc = binascii.crc_hqx(row.to_bytes(), self.__crc)
