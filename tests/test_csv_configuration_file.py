import csv
import struct
from pathlib import Path

import pytest

from ingenialink.csv_configuration_file import CSVConfigurationFile, RegisterRow
from ingenialink.enums.register import RegAccess, RegDtype
from ingenialink.ethercat.register import EthercatRegister

pytest_plugins = ["tests.test_table"]


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


def test_extract_config_table_single_entry(servo_with_table):
    _servo, table = servo_with_table

    index_reg = table.index_register
    value_reg = table.value_register

    csv_cfg = CSVConfigurationFile("unused")
    csv_cfg._CSVConfigurationFile__data.extend([
        RegisterRow(
            f"0x{index_reg.idx:04X}",
            f"0x{index_reg.subidx:02X}",
            "0x00000001",
        ),
        RegisterRow(
            f"0x{value_reg.idx:04X}",
            f"0x{value_reg.subidx:02X}",
            "0x01020304",
        ),
    ])

    config_table = csv_cfg.extract_config_table(table)

    assert config_table.uid == table._Table__dict_table.id
    assert config_table.subnode == (table._Table__dict_table.axis or 0)
    assert len(config_table.elements) == 1

    element = config_table.elements[0]
    assert element.address == 1
    assert element.data == b"\x04\x03\x02\x01"


def test_extract_config_table_multiple_entries(servo_with_table):
    _servo, table = servo_with_table
    index_reg = table.index_register
    value_reg = table.value_register

    csv_cfg = CSVConfigurationFile("unused")
    csv_cfg._CSVConfigurationFile__data.extend([
        RegisterRow(f"0x{index_reg.idx:04X}", f"0x{index_reg.subidx:02X}", "0x00000000"),
        RegisterRow(f"0x{value_reg.idx:04X}", f"0x{value_reg.subidx:02X}", "0xAAAAAAAA"),
        RegisterRow(f"0x{index_reg.idx:04X}", f"0x{index_reg.subidx:02X}", "0x00000001"),
        RegisterRow(f"0x{value_reg.idx:04X}", f"0x{value_reg.subidx:02X}", "0xBBBBBBBB"),
    ])

    config_table = csv_cfg.extract_config_table(table)

    assert len(config_table.elements) == 2
    assert [e.address for e in config_table.elements] == [0, 1]
    assert config_table.elements[0].data == b"\xaa\xaa\xaa\xaa"
    assert config_table.elements[1].data == b"\xbb\xbb\xbb\xbb"


def test_extract_config_table_value_before_index_raises(servo_with_table):
    _servo, table = servo_with_table
    value_reg = table.value_register

    csv_cfg = CSVConfigurationFile("unused")
    csv_cfg._CSVConfigurationFile__data.append(
        RegisterRow(
            f"0x{value_reg.idx:04X}",
            f"0x{value_reg.subidx:02X}",
            "0x01020304",
        )
    )

    with pytest.raises(ValueError, match="Value register row found before index"):
        csv_cfg.extract_config_table(table)
