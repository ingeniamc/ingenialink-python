import logging
from typing import Final
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
from ingenialink.enums.register import RegAddressType
from ingenialink.ethercat.dictionary import EthercatDictionaryV3
from ingenialink.register import Register
from ingenialink.utils._utils import convert_bytes_to_dtype


class RegisterXCFElementFactory:
    DEFAULT_ATTRIBUTES: Final[dict] = {
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
    """Test TableElement.from_xcf method."""
    xml = '<Element address="5" data="deadbeef"/>'
    element = ElementTree.fromstring(xml)
    table_elem = TableElement.from_xcf(element)

    assert table_elem.address == 5
    assert table_elem.data == bytes.fromhex("deadbeef")


def test_table_element_to_xcf():
    """Test TableElement.to_xcf method."""
    table_elem = TableElement(address=10, data=bytes.fromhex("1234abcd"))
    xml_elem = table_elem.to_xcf()

    assert xml_elem.attrib["address"] == "10"
    assert xml_elem.attrib["data"] == "1234abcd"


def test_config_table_from_xcf():
    """Test ConfigTable.from_xcf method."""
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
    """Test ConfigTable.to_xcf method."""
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


def test_configuration_file_with_tables(tmp_path, xcf_schema):
    """Test saving and loading ConfigurationFile with ConfigTable entries."""
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
    xcf_schema.validate(str(xcf_path))

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
    """Test ConfigRegister.from_xcf reads data attribute as bytes."""
    xml = (
        '<Register id="0x2000" subnode="0" dtype="u32" access="rw" storage="165" data="01020304" />'
    )
    element = ElementTree.fromstring(xml)
    reg = ConfigRegister.from_xcf(element)

    assert reg is not None
    assert reg.storage == 165
    assert reg.data == bytes.fromhex("01020304")


def test_register_to_xcf_writes_data_as_hex():
    """Test ConfigRegister.to_xcf writes data attribute as hex string."""
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


def test_config_register_clone_without_overrides():
    """Test ConfigRegister.clone without any attribute overrides."""
    reg = ConfigRegister(
        uid="0x2000",
        subnode=0,
        dtype=RegDtype.U32,
        access=RegAccess.RW,
        storage=1234,
        data=bytes([0xAA, 0xBB, 0xCC]),
    )

    cloned_reg = reg.clone()

    assert cloned_reg.uid == reg.uid
    assert cloned_reg.subnode == reg.subnode
    assert cloned_reg.dtype == reg.dtype
    assert cloned_reg.access == reg.access
    assert cloned_reg.storage == reg.storage
    assert cloned_reg.data == reg.data


def test_config_register_clone_with_overrides():
    """Test ConfigRegister.clone with attribute overrides."""
    reg = ConfigRegister(
        uid="0x2000",
        subnode=0,
        dtype=RegDtype.U32,
        access=RegAccess.RW,
        storage=1234,
        data=bytes([0xAA, 0xBB, 0xCC]),
    )

    cloned_reg = reg.clone(storage=5678, data=bytes([0x11, 0x22, 0x33]))

    assert cloned_reg.uid == reg.uid
    assert cloned_reg.subnode == reg.subnode
    assert cloned_reg.dtype == reg.dtype
    assert cloned_reg.access == reg.access
    assert cloned_reg.storage == 5678
    assert cloned_reg.data == bytes([0x11, 0x22, 0x33])


def test_config_register_clone_can_override_data_with_none() -> None:
    register = ConfigRegister(
        uid="REG",
        subnode=0,
        dtype=RegDtype.U16,
        access=RegAccess.RW,
        storage=0,
        data=b"\x01",
    )

    clone = register.clone(data=None)

    assert clone.data is None
    assert register.data == b"\x01"


def test_config_register_clone_with_storage():
    """Test ConfigRegister.clone_with_storage method."""
    reg = ConfigRegister(
        uid="0x2000",
        subnode=0,
        dtype=RegDtype.U32,
        access=RegAccess.RW,
        storage=1234,
        data=bytes([0xAA, 0xBB, 0xCC]),
    )

    cloned_reg = reg.clone_with_storage(5678)

    assert cloned_reg.uid == reg.uid
    assert cloned_reg.subnode == reg.subnode
    assert cloned_reg.dtype == reg.dtype
    assert cloned_reg.access == reg.access
    assert cloned_reg.storage == 5678
    assert cloned_reg.data is None


def test_configuration_file_clone_copies_mutable_objects_and_reuses_immutable_values():
    """Test ConfigurationFile.clone creates independent configuration objects."""
    configuration = ConfigurationFile.create_empty_configuration(
        Interface.ETH, "TEST-PART", 123, 456, "1.0.0"
    )
    register = ConfigRegister(
        uid="TEST_REG",
        subnode=0,
        dtype=RegDtype.U32,
        access=RegAccess.RW,
        storage=100,
        data=b"\x01\x02",
    )
    table = ConfigTable(
        uid="TEST_TABLE",
        subnode=0,
        elements=[TableElement(address=0, data=b"\x03\x04")],
    )
    configuration.add_config_register(register)
    configuration.add_config_table(table)

    cloned_configuration = configuration.clone()

    assert cloned_configuration is not configuration
    assert cloned_configuration.device is not configuration.device
    assert cloned_configuration.device.interface is configuration.device.interface
    assert cloned_configuration.registers is not configuration.registers
    assert cloned_configuration.registers[0] is not configuration.registers[0]
    assert cloned_configuration.registers[0].dtype is configuration.registers[0].dtype
    assert cloned_configuration.registers[0].access is configuration.registers[0].access
    assert cloned_configuration.registers[0].data is configuration.registers[0].data
    assert cloned_configuration.tables is not configuration.tables
    assert cloned_configuration.tables[0] is not configuration.tables[0]
    assert cloned_configuration.tables[0].elements is not configuration.tables[0].elements
    assert cloned_configuration.tables[0].elements[0] is not configuration.tables[0].elements[0]
    assert (
        cloned_configuration.tables[0].elements[0].data is configuration.tables[0].elements[0].data
    )

    cloned_configuration.device.part_number = "CLONED-PART"
    cloned_configuration.registers[0].storage = 200
    cloned_configuration.tables[0].elements[0].address = 1

    assert configuration.device.part_number == "TEST-PART"
    assert configuration.registers[0].storage == 100
    assert configuration.tables[0].elements[0].address == 0


def test_register_effective_value_with_data_and_storage():
    """Test the effective_value property when both data and storage are present.

    Data should take precedence over storage.
    """
    reg = ConfigRegister(
        uid="0x2000",
        subnode=0,
        dtype=RegDtype.U32,
        access=RegAccess.RW,
        storage=1234,
        data=bytes([0xAA, 0xBB, 0xCC]),
    )
    assert reg.effective_value == convert_bytes_to_dtype(reg.data, reg.dtype)


def test_register_effective_value_with_only_storage():
    """Test the effective_value property when only storage is present.

    Storage should be returned as the effective value.
    """
    reg = ConfigRegister(
        uid="0x2000",
        subnode=0,
        dtype=RegDtype.U32,
        access=RegAccess.RW,
        storage=1234,
        data=None,
    )
    assert reg.effective_value == reg.storage


class TestFromDictionaryDefaults:
    """Tests for ConfigurationFile.from_dictionary_defaults.

    Uses tests.resources.TEST_DICT_ECAT_EOE_v3 (EthercatDictionaryV3) which
    contains exactly 6 registers: 3 qualifying (RW + NVM/NVM_CFG) with defaults,
    2 read-only, and 1 RW non-NVM register.

    Qualifying registers in that file:
        CIA301_COMMS_RPDO1_MAP   (U8,  default=1)
        CIA301_COMMS_RPDO1_MAP_1 (U32, default=268451936)
        COMMU_ANGLE_SENSOR       (U16, default=4)
    """

    def test_from_dictionary_defaults(self):
        """Only RW+NVM registers are included, with their XDF3 defaults and device metadata."""
        dictionary = EthercatDictionaryV3(tests.resources.TEST_DICT_ECAT_EOE_v3, Interface.ECAT)

        conf = ConfigurationFile.from_dictionary_defaults(dictionary)

        # Only the 3 qualifying registers are present — RO and non-NVM registers are excluded
        assert len(conf.registers) == 3
        assert {r.uid for r in conf.registers} == {
            "CIA301_COMMS_RPDO1_MAP",
            "CIA301_COMMS_RPDO1_MAP_1",
            "COMMU_ANGLE_SENSOR",
        }

        # Each register carries its declared XDF3 default value
        reg_map = {r.uid: r.storage for r in conf.registers}
        assert reg_map["CIA301_COMMS_RPDO1_MAP"] == 1
        assert reg_map["CIA301_COMMS_RPDO1_MAP_1"] == 268451936
        assert reg_map["COMMU_ANGLE_SENSOR"] == 4

        # Non-qualifying registers from the dictionary must not appear in the result
        excluded_uids = {
            r.identifier
            for r in dictionary.all_registers()
            if r.access != RegAccess.RW
            or r.address_type not in (RegAddressType.NVM_CFG, RegAddressType.NVM)
        }
        assert not ({r.uid for r in conf.registers} & excluded_uids)

        # Device metadata is copied from the dictionary
        assert conf.device.interface == Interface.ECAT
        assert conf.device.part_number == dictionary.part_number
        assert conf.device.product_code == dictionary.product_code
        assert conf.device.revision_number == dictionary.revision_number
        assert conf.device.firmware_version == dictionary.firmware_version


class TestOverrideValues:
    """Tests for ConfigurationFile.override_values."""

    def test_replaces_matching_register(self):
        """A register matching by (subnode, uid) has its value replaced."""
        base = ConfigurationFile.create_empty_configuration(
            interface=Interface.ETH,
            part_number=None,
            product_code=None,
            revision_number=None,
            firmware_version=None,
        )
        base.add_config_register(
            ConfigRegister("REG_A", subnode=1, dtype=RegDtype.U16, access=RegAccess.RW, storage=10)
        )

        override = ConfigurationFile.create_empty_configuration(
            interface=Interface.ETH,
            part_number=None,
            product_code=None,
            revision_number=None,
            firmware_version=None,
        )
        override.add_config_register(
            ConfigRegister("REG_A", subnode=1, dtype=RegDtype.U16, access=RegAccess.RW, storage=99)
        )

        base.override_values(override)

        assert len(base.registers) == 1
        assert base.registers[0].storage == 99

    def test_adds_non_matching_register_with_warning(self, caplog):
        """A register not present in base is added, and a warning is logged."""
        base = ConfigurationFile.create_empty_configuration(
            interface=Interface.ETH,
            part_number=None,
            product_code=None,
            revision_number=None,
            firmware_version=None,
        )
        base.add_config_register(
            ConfigRegister("REG_A", subnode=1, dtype=RegDtype.U16, access=RegAccess.RW, storage=1)
        )

        override = ConfigurationFile.create_empty_configuration(
            interface=Interface.ETH,
            part_number=None,
            product_code=None,
            revision_number=None,
            firmware_version=None,
        )
        override.add_config_register(
            ConfigRegister(
                "REG_NEW", subnode=1, dtype=RegDtype.U16, access=RegAccess.RW, storage=77
            )
        )

        with caplog.at_level(logging.WARNING):
            base.override_values(override)

        assert len(base.registers) == 2
        assert base.registers[1].uid == "REG_NEW"
        assert any("REG_NEW" in record.message for record in caplog.records)

    def test_replaces_matching_table(self):
        """A table matching by (subnode, uid) has its content replaced."""
        base = ConfigurationFile.create_empty_configuration(
            interface=Interface.ETH,
            part_number=None,
            product_code=None,
            revision_number=None,
            firmware_version=None,
        )
        base.add_register(Register(RegDtype.U16, RegAccess.RW, "REG", subnode=0), 0)
        base.add_config_table(
            ConfigTable(uid="TABLE_A", subnode=0, elements=[TableElement(0, b"\x01")])
        )

        override = ConfigurationFile.create_empty_configuration(
            interface=Interface.ETH,
            part_number=None,
            product_code=None,
            revision_number=None,
            firmware_version=None,
        )
        override.add_config_table(
            ConfigTable(uid="TABLE_A", subnode=0, elements=[TableElement(0, b"\xff")])
        )

        base.override_values(override)

        assert len(base.tables) == 1
        assert base.tables[0].elements[0].data == b"\xff"

    def test_adds_non_matching_table_with_debug_log(self, caplog):
        """A table not present in base is added, and a debug message is logged."""
        base = ConfigurationFile.create_empty_configuration(
            interface=Interface.ETH,
            part_number=None,
            product_code=None,
            revision_number=None,
            firmware_version=None,
        )
        base.add_register(Register(RegDtype.U16, RegAccess.RW, "REG", subnode=0), 0)

        override = ConfigurationFile.create_empty_configuration(
            interface=Interface.ETH,
            part_number=None,
            product_code=None,
            revision_number=None,
            firmware_version=None,
        )
        override.add_config_table(
            ConfigTable(uid="TABLE_NEW", subnode=0, elements=[TableElement(0, b"\xab")])
        )

        with caplog.at_level(logging.DEBUG):
            base.override_values(override)

        assert len(base.tables) == 1
        assert base.tables[0].uid == "TABLE_NEW"
        assert any(
            "TABLE_NEW" in record.message and record.levelno == logging.DEBUG
            for record in caplog.records
        )


def test_clone_copies_mutable_configuration_data() -> None:
    base = ConfigurationFile.create_empty_configuration(
        interface=Interface.ETH,
        part_number=None,
        product_code=None,
        revision_number=None,
        firmware_version=None,
    )
    base.add_register(Register(RegDtype.U16, RegAccess.RW, "REG", subnode=0), 0)
    base.add_config_table(
        ConfigTable(uid="TABLE_A", subnode=0, elements=[TableElement(0, b"\x01")])
    )

    clone = base.clone()

    # Ensure the clone is a different object
    assert clone is not base
    # Ensure mutable configuration data is copied
    assert clone.registers is not base.registers
    assert clone.tables is not base.tables
    assert clone.device is not base.device
    assert clone.tables[0].elements is not base.tables[0].elements
    # Ensure the content is the same
    assert clone.registers[0].uid == base.registers[0].uid
    assert clone.tables[0].uid == base.tables[0].uid

    clone.registers[0].storage = 1
    clone.tables[0].elements[0].data = b"\xff"
    assert base.registers[0].storage == 0
    assert base.tables[0].elements[0].data == b"\x01"


def test_find_registers_returns_registers_with_matching_uid() -> None:
    """Test that find_registers returns all registers with the specified UID."""
    configuration = ConfigurationFile.create_empty_configuration(
        interface=Interface.ETH,
        part_number=None,
        product_code=None,
        revision_number=None,
        firmware_version=None,
    )
    configuration.add_config_register(
        ConfigRegister("REG", 0, RegDtype.U16, RegAccess.RW, storage=0)
    )
    configuration.add_config_register(
        ConfigRegister("REG", 1, RegDtype.U16, RegAccess.RW, storage=1)
    )
    configuration.add_config_register(
        ConfigRegister("OTHER", 0, RegDtype.U16, RegAccess.RW, storage=2)
    )

    assert list(configuration.find_registers("REG")) == configuration.registers[:2]


def test_find_register_returns_register_for_subnode() -> None:
    """Test that find_register returns the correct register for a given subnode."""
    configuration = ConfigurationFile.create_empty_configuration(
        interface=Interface.ETH,
        part_number=None,
        product_code=None,
        revision_number=None,
        firmware_version=None,
    )
    register = ConfigRegister("REG", 1, RegDtype.U16, RegAccess.RW, storage=1)
    configuration.add_config_register(register)

    assert configuration.find_register("REG", subnode=1) is register
    assert configuration.find_register("REG") is register


def test_find_register_raises_for_missing_or_ambiguous_register() -> None:
    """Test that find_register raises appropriate exceptions for missing or ambiguous registers."""
    configuration = ConfigurationFile.create_empty_configuration(
        interface=Interface.ETH,
        part_number=None,
        product_code=None,
        revision_number=None,
        firmware_version=None,
    )
    configuration.add_config_register(
        ConfigRegister("REG", 0, RegDtype.U16, RegAccess.RW, storage=0)
    )
    configuration.add_config_register(
        ConfigRegister("REG", 1, RegDtype.U16, RegAccess.RW, storage=1)
    )

    with pytest.raises(ValueError, match="multiple subnodes"):
        configuration.find_register("REG")
    with pytest.raises(KeyError, match="subnode=2"):
        configuration.find_register("REG", subnode=2)
    with pytest.raises(ValueError, match="not found"):
        configuration.find_register("MISSING")
