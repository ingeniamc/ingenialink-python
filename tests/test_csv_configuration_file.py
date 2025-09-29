import csv
import struct
from pathlib import Path

import pytest

from ingenialink.csv_configuration_file import CSVConfigurationFile, RegisterRow
from ingenialink.enums.register import RegAccess, RegDtype
from ingenialink.ethercat.register import EthercatRegister


@pytest.mark.no_connection
def test_register_row_formatting():
    reg = EthercatRegister(0x2025, 0x00, RegDtype.U32, RegAccess.RW)
    row = RegisterRow.from_register(reg, b"\x00\x00\xa0A")
    assert row.index == "0x2025"
    assert row.subindex == "0x00"
    assert row.value == "0x41A00000"
    assert row.csv_row == ["0x2025", "0x00", "0x41A00000"]
    assert row.to_bytes() == b"0x2025,0x00,0x41A00000"


@pytest.mark.no_connection
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


@pytest.mark.no_connection
def test_format_value_for_csv():
    reg = EthercatRegister(0x2025, 0x00, RegDtype.U32, RegAccess.RW)
    register_float_value = 20.0
    raw_value_little_endian = struct.pack("f", register_float_value)
    garbage_bytes = b"\xff\xff"
    raw_register_bytes = raw_value_little_endian + garbage_bytes
    row = RegisterRow.from_register(reg, raw_register_bytes)
    expected_value_big_endian = struct.pack(">f", register_float_value)
    assert row.value == f"0x{expected_value_big_endian.hex().upper()}"
