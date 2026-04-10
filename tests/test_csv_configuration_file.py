import csv
import struct
from dataclasses import dataclass
from pathlib import Path

from ingenialink.csv_configuration_file import CSVConfigurationFile, RegisterRow
from ingenialink.enums.register import RegAccess, RegDtype
from ingenialink.ethercat.register import EthercatRegister


@dataclass(frozen=True)
class DummyRegister:
    idx: int
    subidx: int
    dtype: RegDtype
    identifier: str


class DummyTable:
    def __init__(
        self,
        index_register: DummyRegister,
        value_register: DummyRegister,
        raw_values: dict[int, bytes],
    ) -> None:
        self.index_register = index_register
        self.value_register = value_register
        self._raw_values = raw_values

    def get_value_raw(self, index: int) -> bytes:
        try:
            return self._raw_values[index]
        except KeyError as exc:
            raise IndexError(f"Table address {index} not found.") from exc


def test_register_row_formatting():
    reg = EthercatRegister(0x2025, 0x00, RegDtype.U32, RegAccess.RW)
    row = RegisterRow.from_register(reg, b"\x00\x00\xa0A")
    assert row.index == "0x2025"
    assert row.subindex == "0x00"
    assert row.value == "0x41A00000"
    assert row.csv_row == ["0x2025", "0x00", "0x41A00000"]
    assert row.to_bytes() == b"0x2025,0x00,0x41A00000"


def test_csv_configuration_file(tmp_path: Path):
    file_path = tmp_path / "config.csv"
    cfg = CSVConfigurationFile(str(file_path))
    reg1 = EthercatRegister(0x2025, 0x00, RegDtype.U32, RegAccess.RW)
    reg2 = EthercatRegister(0x209A, 0x00, RegDtype.U32, RegAccess.RW)
    cfg.add_register(reg1, b"\x00\x00\xa0A")
    cfg.add_register(reg2, b"\x00\x00\x80?")
    cfg.write_to_file()
    with file_path.open() as f:
        reader = csv.reader(f)
        header = next(reader)
        crc_line = next(reader)
        data_rows = list(reader)
    assert header == ["v1"]
    assert crc_line == ["0x31E8"]
    assert data_rows == [["0x2025", "0x00", "0x41A00000"], ["0x209A", "0x00", "0x3F800000"]]


def test_format_value_for_csv():
    reg = EthercatRegister(0x2025, 0x00, RegDtype.U32, RegAccess.RW)
    register_float_value = 20.0
    raw_value_little_endian = struct.pack("f", register_float_value)
    garbage_bytes = b"\xff\xff"
    raw_register_bytes = raw_value_little_endian + garbage_bytes
    row = RegisterRow.from_register(reg, raw_register_bytes)
    expected_value_big_endian = struct.pack(">f", register_float_value)
    assert row.value == f"0x{expected_value_big_endian.hex().upper()}"


def test_load_from_csv_reads_rows(tmp_path: Path):
    file_path = tmp_path / "load_config.csv"
    file_path.write_text("v1\n0x0000\n0x2025,0x00,0x41A00000\n0x209A,0x00,0x3F800000\n")

    cfg = CSVConfigurationFile.load_from_csv(str(file_path))

    assert cfg._CSVConfigurationFile__crc == 0x0000
    assert [row.csv_row for row in cfg._CSVConfigurationFile__data] == [
        ["0x2025", "0x00", "0x41A00000"],
        ["0x209A", "0x00", "0x3F800000"],
    ]


def test_compare_with_table_reports_no_mismatches_for_matching_values():
    csv_cfg = CSVConfigurationFile("unused")
    csv_cfg._CSVConfigurationFile__data.extend([
        RegisterRow("0x1000", "0x00", "0x00000001"),
        RegisterRow("0x1001", "0x00", "0x01020304"),
    ])

    index_register = DummyRegister(idx=0x1000, subidx=0x00, dtype=RegDtype.U32, identifier="INDEX")
    value_register = DummyRegister(idx=0x1001, subidx=0x00, dtype=RegDtype.U32, identifier="VALUE")
    table = DummyTable(index_register, value_register, {1: b"\x04\x03\x02\x01"})

    mismatches = csv_cfg.compare_with_table(table)

    assert mismatches == []


def test_compare_with_table_reports_mismatches_for_differing_values():
    csv_cfg = CSVConfigurationFile("unused")
    csv_cfg._CSVConfigurationFile__data.extend([
        RegisterRow("0x1000", "0x00", "0x00000001"),
        RegisterRow("0x1001", "0x00", "0x01020304"),
    ])

    index_register = DummyRegister(idx=0x1000, subidx=0x00, dtype=RegDtype.U32, identifier="INDEX")
    value_register = DummyRegister(idx=0x1001, subidx=0x00, dtype=RegDtype.U32, identifier="VALUE")
    table = DummyTable(index_register, value_register, {1: b"\x08\x07\x06\x05"})

    mismatches = csv_cfg.compare_with_table(table)

    assert mismatches == ["Table VALUE address 1 --- Expected: 0x01020304 Found: 0x05060708"]
