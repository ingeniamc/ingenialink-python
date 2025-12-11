from typing import ClassVar
from xml.etree import ElementTree

import pytest

import tests.resources
from ingenialink import RegAccess, RegDtype
from ingenialink.configuration_file import (
    ConfigRegister,
    ConfigTable,
    ConfigurationFile,
    TableElement,
)
from ingenialink.dictionary import Interface
from ingenialink.register import Register


class RegisterXCFElementFactory:
    DEFAULT_ATTRIBUTES: ClassVar[dict] = {
        ConfigRegister._ConfigRegister__ID_ATTR: "PROF_MAX_VEL",
        ConfigRegister._ConfigRegister__SUBNODE_ATTR: "1",
        ConfigRegister._ConfigRegister__DTYPE_ATTR: "float",
        ConfigRegister._ConfigRegister__ACCESS_ATTR: "rw",
        ConfigRegister._ConfigRegister__STORAGE_ATTR: "20.0",
    }

    @classmethod
    def create(cls, missing_attibute):
        attrs = cls.DEFAULT_ATTRIBUTES.copy()

        if missing_attibute is not None:
            attrs.pop(missing_attibute)

        return ElementTree.Element("Register", attrib=attrs)


def test_from_xcf():
    test_file = tests.resources.TEST_CONFIG_FILE
    conf_file = ConfigurationFile.load_from_xcf(test_file)
    assert conf_file.device.interface == Interface.CAN
    assert conf_file.device.part_number == "EVE-NET-C"
    assert conf_file.device.product_code == 493840
    assert conf_file.device.revision_number == 196634
    assert conf_file.device.firmware_version == "2.3.0"
    assert conf_file.device.node_id is None

    assert len(conf_file.registers) == 1  # Only 1 register has storage field
    assert conf_file.registers[0].dtype == RegDtype.U16
    assert conf_file.registers[0].access == RegAccess.RW
    assert conf_file.registers[0].uid == "DRV_DIAG_SYS_ERROR_TOTAL_COM"
    assert conf_file.registers[0].subnode == 0
    assert conf_file.registers[0].storage == 0


def test_from_register():
    conf_file = ConfigurationFile.create_empty_configuration(Interface.CAN, "a", 0, 0, "0.0.0")
    reg = Register(RegDtype.FLOAT, RegAccess.RW, "TEST_REG", subnode=2)
    conf_file.add_register(reg, 5.5)
    assert conf_file.registers[0].dtype == RegDtype.FLOAT
    assert conf_file.registers[0].access == RegAccess.RW
    assert conf_file.registers[0].uid == "TEST_REG"
    assert conf_file.registers[0].subnode == 2
    assert conf_file.registers[0].storage == 5.5


def test_to_xcf_fail_no_device():
    with pytest.raises(ValueError):
        conf = ConfigurationFile.create_empty_configuration(Interface.CAN, "a", 0, 0, "0.0.0")
        conf.save_to_xcf("test_path")


@pytest.mark.parametrize("missing_attr", RegisterXCFElementFactory.DEFAULT_ATTRIBUTES.keys())
def test_config_register_from_xcf_missing_attribute(missing_attr):
    register_xcf_element = RegisterXCFElementFactory.create(missing_attr)
    with pytest.raises(ValueError) as exc_info:
        ConfigRegister.from_xcf(register_xcf_element)

    error_msg = str(exc_info.value)
    if missing_attr == ConfigRegister._ConfigRegister__ID_ATTR:
        assert error_msg == "Missing id attribute in register"
    else:
        expected = f"Missing {missing_attr} attribute in register"
        if register_xcf_element.attrib.get("id"):
            expected += f" for {register_xcf_element.attrib.get('id')}"
        assert error_msg == expected


def test_table_element_from_xcf():
    xml = '<Element address="5" data="deadbeef"/>'
    element = ElementTree.fromstring(xml)
    table_elem = TableElement.from_xcf(element)

    assert table_elem.address == 5
    assert table_elem.data == bytes.fromhex("deadbeef")


def test_table_element_to_xcf():
    table_elem = TableElement(address=10, data=bytes.fromhex("1234abcd"))
    xml_elem = table_elem.to_xcf()

    assert xml_elem.attrib["address"] == "10"
    assert xml_elem.attrib["data"] == "1234abcd"


def test_config_table_from_xcf():
    xml = """<Table id="MEM_USR" subnode="0">
        <Element address="0" data="1234"/>
        <Element address="1" data="5678"/>
        <Element address="2" data="abcd"/>
    </Table>"""
    element = ElementTree.fromstring(xml)
    table = ConfigTable.from_xcf(element)

    assert table.uid == "MEM_USR"
    assert table.subnode == 0
    assert len(table.elements) == 3
    assert table.elements[0].address == 0
    assert table.elements[0].data == bytes.fromhex("1234")
    assert table.elements[2].address == 2
    assert table.elements[2].data == bytes.fromhex("abcd")


def test_config_table_to_xcf():
    table = ConfigTable(uid="TEST_TABLE", subnode=1)
    table.elements.append(TableElement(0, bytes.fromhex("aa")))
    table.elements.append(TableElement(1, bytes.fromhex("bb")))

    xml_elem = table.to_xcf()

    assert xml_elem.attrib["id"] == "TEST_TABLE"
    assert xml_elem.attrib["subnode"] == "1"
    elements = xml_elem.findall("Element")
    assert len(elements) == 2
    assert elements[0].attrib["address"] == "0"
    assert elements[0].attrib["data"] == "aa"
    assert elements[1].attrib["address"] == "1"
    assert elements[1].attrib["data"] == "bb"


def test_configuration_file_with_tables(tmp_path):
    # Create XCF with tables
    conf_file = ConfigurationFile.create_empty_configuration(
        Interface.ETH, "TEST-PART", 123, 456, "1.0.0"
    )

    # Add a register
    reg = Register(RegDtype.U32, RegAccess.RW, "TEST_REG", subnode=0)
    conf_file.add_register(reg, 100)

    # Add a table
    table = ConfigTable(uid="MEM_USR", subnode=0)
    table.elements.append(TableElement(0, bytes.fromhex("11223344")))
    table.elements.append(TableElement(1, bytes.fromhex("55667788")))
    conf_file.add_config_table(table)

    # Save and reload
    xcf_path = tmp_path / "test_with_tables.xcf"
    conf_file.save_to_xcf(str(xcf_path))

    loaded_conf = ConfigurationFile.load_from_xcf(str(xcf_path))

    # Verify registers
    assert len(loaded_conf.registers) == 1
    assert loaded_conf.registers[0].uid == "TEST_REG"

    # Verify tables
    assert len(loaded_conf.tables) == 1
    assert loaded_conf.tables[0].uid == "MEM_USR"
    assert loaded_conf.tables[0].subnode == 0
    assert len(loaded_conf.tables[0].elements) == 2
    assert loaded_conf.tables[0].elements[0].address == 0
    assert loaded_conf.tables[0].elements[0].data == bytes.fromhex("11223344")
    assert loaded_conf.tables[0].elements[1].address == 1
    assert loaded_conf.tables[0].elements[1].data == bytes.fromhex("55667788")


def test_register_from_xcf_reads_data_attribute():
    # register element with only data attribute (no storage)
    xml = (
        '<Register id="0x2000" subnode="0" dtype="u32" access="rw" storage="165" data="01020304" />'
    )
    element = ElementTree.fromstring(xml)
    reg = ConfigRegister.from_xcf(element)

    assert reg is not None
    assert reg.storage == 165
    assert reg.data == bytes.fromhex("01020304")


def test_register_to_xcf_writes_data_as_hex():
    # create a register with storage None and data bytes
    reg = ConfigRegister(
        uid="0x2000",
        subnode=0,
        dtype=RegDtype.U32,
        access=RegAccess.RW,
        storage=1234,
        data=bytes([0xAA, 0xBB, 0xCC]),
    )

    element = reg.to_xcf()
    # storage should always be present
    assert element.get("storage") == "1234"
    # data must be hex string matching the bytes
    assert element.get("data") == "aabbcc"
