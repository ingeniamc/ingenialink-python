import tempfile
from os.path import join as join_path
from xml.dom import minidom
from xml.etree import ElementTree

import pytest
import virtual_drive.resources

import tests.resources.canopen
from ingenialink.canopen.dictionary import CanopenDictionaryV2, CanopenDictionaryV3
from ingenialink.canopen.register import CanopenRegister
from ingenialink.dictionary import (
    CanOpenObject,
    CanOpenObjectType,
    DictionaryDescriptor,
    DictionaryV2,
    DictionaryV3,
    ILDictionaryParseError,
    Interface,
)
from ingenialink.enums.register import RegAccess, RegDtype
from ingenialink.ethercat.dictionary import EthercatDictionaryV2, EthercatDictionaryV3
from ingenialink.ethernet.dictionary import (
    EoEDictionaryV3,
    EthernetDictionaryV2,
)
from ingenialink.servo import DictionaryFactory


@pytest.mark.parametrize(
    "dict_path, interface, fw_version, product_code, part_number, revision_number",
    [
        (
            tests.resources.canopen.TEST_DICT_CAN_V3,
            Interface.CAN,
            "2.4.1",
            61939713,
            "EVS-NET-C",
            196617,
        ),
        (
            tests.resources.comkit.COM_KIT_DICT,
            Interface.ETH,
            "1.4.7",
            123456789,
            None,
            12345,
        ),
        (
            tests.resources.ethercat.TEST_DICT_ETHERCAT,
            Interface.ECAT,
            "2.0.1",
            57745409,
            "CAP-NET-E",
            196635,
        ),
        (
            tests.resources.ethercat.TEST_DICT_ETHERCAT,
            Interface.ETH,
            "2.0.1",
            57745409,
            "CAP-NET-E",
            196635,
        ),
    ],
)
def test_dictionary_description(
    dict_path, interface, fw_version, product_code, part_number, revision_number
):
    dict_description = DictionaryFactory.get_dictionary_description(dict_path, interface)
    assert dict_description == DictionaryDescriptor(
        firmware_version=fw_version,
        product_code=product_code,
        part_number=part_number,
        revision_number=revision_number,
    )


@pytest.mark.parametrize(
    "dict_path, interfaces, fw_version, product_code, "
    "part_number, revision_number, mayor_version, image",
    [
        (
            tests.resources.canopen.TEST_DICT_CAN_V3,
            [Interface.CAN, Interface.ETH],
            "2.4.1",
            61939713,
            "EVS-NET-C",
            196617,
            3,
            b"",
        ),
        (
            tests.resources.comkit.COM_KIT_DICT,
            [Interface.ETH],
            "1.4.7",
            123456789,
            None,
            12345,
            2,
            b"",
        ),
        (
            tests.resources.ethercat.TEST_DICT_ETHERCAT,
            [Interface.ETH],  # ECAT and EoE are mapped to ETH upon reading
            "2.0.1",
            57745409,
            "CAP-NET-E",
            196635,
            2,
            b"",
        ),
        (
            tests.resources.ethercat.TEST_DICT_ETHERCAT,
            [Interface.ETH],
            "2.0.1",
            57745409,
            "CAP-NET-E",
            196635,
            2,
            b"",
        ),
    ],
)
def test_dictionary_all_descriptions(
    dict_path,
    interfaces,
    fw_version,
    product_code,
    part_number,
    revision_number,
    mayor_version,
    image,
):
    """Test getting all dictionary descriptions for all interfaces supported by the dictionary."""
    dict_description = DictionaryFactory.get_all_dictionary_descriptions(dict_path)
    # Assert version and image are correct for all interfaces
    assert dict_description.mayor_version == mayor_version
    assert dict_description.image == image
    # Assert interface-specific attributes are correct
    for interface in interfaces:
        test_interface = DictionaryDescriptor(
            firmware_version=fw_version,
            product_code=product_code,
            part_number=part_number,
            revision_number=revision_number,
            interface=interface,
        )
        assert test_interface in dict_description.interface_descriptor


@pytest.mark.parametrize(
    "dict_path, register_uid, axis, dict_type",
    [
        (tests.resources.DEN_NET_E_2_8_0_xdf_v3, "DRV_AXIS_NUMBER", 0, DictionaryV3),
        (tests.resources.ethercat.TEST_DICT_ETHERCAT, "MON_CFG_EOC_TYPE", 0, DictionaryV2),
    ],
)
def test_dictionary_parses_register_units_to_none(
    dict_path: str, register_uid: str, axis: int, dict_type: type[DictionaryV3]
) -> None:
    """Test that registers with 'none' units are parsed correctly to None.

    Test for both DictionaryV2 and DictionaryV3.
    """
    dictionary = DictionaryFactory.create_dictionary(dict_path, Interface.ECAT)
    assert isinstance(dictionary, dict_type)

    register = dictionary.get_register(register_uid, axis=axis)
    assert register.units is None


@pytest.mark.parametrize(
    "dict_path, interface, raises",
    [
        (tests.resources.canopen.TEST_DICT_CAN_V3, Interface.ECAT, ILDictionaryParseError),
        (tests.resources.canopen.TEST_DICT_CAN, Interface.ECAT, ILDictionaryParseError),
        (tests.resources.TEST_DICT_ECAT_EOE_v3, Interface.CAN, ILDictionaryParseError),
        (tests.resources.ethercat.TEST_DICT_ETHERCAT, Interface.CAN, ILDictionaryParseError),
        ("/invented/path/test_no_dict.xdf", Interface.ECAT, FileNotFoundError),
    ],
)
def test_dictionary_description_fail(dict_path, interface, raises):
    with pytest.raises(raises):
        DictionaryFactory.get_dictionary_description(dict_path, interface)


@pytest.mark.parametrize(
    "dictionary_class, dictionary_path",
    [
        (CanopenDictionaryV2, tests.resources.canopen.TEST_DICT_CAN),
        (EthernetDictionaryV2, tests.resources.ethernet.TEST_DICT_ETHERNET),
    ],
)
def test_dictionary_v2_image(dictionary_class, dictionary_path):
    dictionary = dictionary_class(dictionary_path)
    assert isinstance(dictionary.image, str)


@pytest.mark.parametrize(
    "dictionary_class, dictionary_path",
    [
        (CanopenDictionaryV2, tests.resources.canopen.TEST_DICT_CAN),
        (EthernetDictionaryV2, tests.resources.ethernet.TEST_DICT_ETHERNET),
    ],
)
def test_dictionary_v2_image_none(dictionary_class, dictionary_path):
    with open(dictionary_path, encoding="utf-8") as xdf_file:
        tree = ElementTree.parse(xdf_file)
    root = tree.getroot()
    root.remove(root.find(DictionaryV2._DictionaryV2__DICT_IMAGE))
    xml_str = minidom.parseString(ElementTree.tostring(root)).toprettyxml(
        indent="  ", newl="", encoding="UTF-8"
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_file = join_path(tmp_dir, "temp.xdf")
        with open(temp_file, "wb") as merged_file:
            merged_file.write(xml_str)
        dictionary = dictionary_class(temp_file)

    assert dictionary.image is None


@pytest.mark.parametrize(
    "dict_path, interface, dict_class",
    [
        (tests.resources.canopen.TEST_DICT_CAN, Interface.CAN, CanopenDictionaryV2),
        (tests.resources.canopen.TEST_DICT_CAN_V3, Interface.CAN, CanopenDictionaryV3),
        (tests.resources.ethercat.TEST_DICT_ETHERCAT, Interface.ECAT, EthercatDictionaryV2),
        (tests.resources.ethernet.TEST_DICT_ETHERNET, Interface.ETH, EthernetDictionaryV2),
        (tests.resources.ethercat.TEST_DICT_ETHERCAT, Interface.EoE, EthernetDictionaryV2),
        (tests.resources.TEST_DICT_ECAT_EOE_v3, Interface.ECAT, EthercatDictionaryV3),
        (tests.resources.TEST_DICT_ECAT_EOE_v3, Interface.EoE, EoEDictionaryV3),
        (tests.resources.TEST_DICT_ECAT_EOE_SAFE_v3, Interface.ECAT, EthercatDictionaryV3),
        (tests.resources.TEST_DICT_ECAT_EOE_SAFE_v3, Interface.EoE, EoEDictionaryV3),
    ],
)
def test_dictionary_factory(dict_path, interface, dict_class):
    test_dict = DictionaryFactory.create_dictionary(dict_path, interface)
    assert isinstance(test_dict, dict_class)


@pytest.mark.parametrize(
    "dict_path, interface, raises",
    [
        (tests.resources.canopen.TEST_DICT_CAN, Interface.ETH, ILDictionaryParseError),
        (tests.resources.canopen.TEST_DICT_CAN_V3, Interface.ECAT, ILDictionaryParseError),
        (tests.resources.ethercat.TEST_DICT_ETHERCAT, Interface.CAN, ILDictionaryParseError),
        (tests.resources.ethernet.TEST_DICT_ETHERNET, Interface.CAN, ILDictionaryParseError),
        (tests.resources.ethercat.TEST_DICT_ETHERCAT, Interface.CAN, ILDictionaryParseError),
        (tests.resources.TEST_DICT_ECAT_EOE_v3, Interface.ETH, ILDictionaryParseError),
        (tests.resources.TEST_DICT_ECAT_EOE_v3, Interface.CAN, ILDictionaryParseError),
    ],
)
def test_dictionary_interface_mismatch(dict_path, interface, raises):
    with pytest.raises(raises):
        DictionaryFactory.create_dictionary(dict_path, interface)


def test_merge_dictionaries_registers():
    coco_dict_path = tests.resources.comkit.COM_KIT_DICT
    moco_dict_path = tests.resources.comkit.CORE_DICT
    coco_dict = EthernetDictionaryV2(coco_dict_path)
    moco_dict = EthernetDictionaryV2(moco_dict_path)
    coco_subnode_0_num_regs = len(coco_dict.registers(0))
    assert coco_subnode_0_num_regs == 1
    coco_subnode_1_num_regs = len(coco_dict.registers(1))
    assert coco_subnode_1_num_regs == 0
    moco_subnode_0_num_regs = len(moco_dict.registers(0))
    assert moco_subnode_0_num_regs == 0
    moco_subnode_1_num_regs = len(moco_dict.registers(1))
    assert moco_subnode_1_num_regs == 1
    merged_dict = coco_dict + moco_dict
    merged_dict_subnode_0_num_regs = len(merged_dict.registers(0))
    assert merged_dict_subnode_0_num_regs == coco_subnode_0_num_regs + moco_subnode_0_num_regs
    merged_dict_subnode_1_num_regs = len(merged_dict.registers(1))
    assert merged_dict_subnode_1_num_regs == coco_subnode_1_num_regs + moco_subnode_1_num_regs


def test_merge_dictionaries_errors():
    coco_dict_path = tests.resources.comkit.COM_KIT_DICT
    moco_dict_path = tests.resources.comkit.CORE_DICT
    coco_dict = EthernetDictionaryV2(coco_dict_path)
    moco_dict = EthernetDictionaryV2(moco_dict_path)
    coco_num_errors = len(coco_dict.errors)
    assert coco_num_errors == 1
    moco_num_errors = len(moco_dict.errors)
    assert moco_num_errors == 1
    merged_dict = coco_dict + moco_dict
    merged_dict_num_errors = len(merged_dict.errors)
    assert merged_dict_num_errors == coco_num_errors + moco_num_errors


def test_merge_dictionaries_attributes():
    coco_dict_path = tests.resources.comkit.COM_KIT_DICT
    moco_dict_path = tests.resources.comkit.CORE_DICT
    coco_dict = EthernetDictionaryV2(coco_dict_path)
    assert coco_dict.product_code == 123456789
    assert coco_dict.revision_number == 12345
    assert coco_dict.firmware_version == "1.4.7"
    assert coco_dict.part_number is None
    moco_dict = EthernetDictionaryV2(moco_dict_path)
    assert moco_dict.product_code == 987654321
    assert moco_dict.revision_number == 31
    assert moco_dict.firmware_version == "2.4.0"
    assert moco_dict.part_number == "CORE"
    merged_dict = coco_dict + moco_dict
    assert merged_dict.product_code == 987654321
    assert merged_dict.revision_number == 31
    assert merged_dict.firmware_version == "2.4.0"
    assert merged_dict.part_number == "CORE"
    assert merged_dict.coco_product_code == 123456789


def test_merge_dictionaries_image():
    coco_dict_path = tests.resources.comkit.COM_KIT_DICT
    moco_dict_path = tests.resources.comkit.CORE_DICT
    coco_dict = EthernetDictionaryV2(coco_dict_path)
    moco_dict = EthernetDictionaryV2(moco_dict_path)
    assert coco_dict.image is None
    assert isinstance(moco_dict.image, str)
    merged_dict = coco_dict + moco_dict
    assert merged_dict.image == moco_dict.image


def test_merge_dictionaries_tables():
    """Test that tables are merged when using + operator."""
    coco_dict_path = tests.resources.comkit.COM_KIT_DICT
    moco_dict_path = tests.resources.comkit.CORE_DICT
    coco_dict = EthernetDictionaryV2(coco_dict_path)
    moco_dict = EthernetDictionaryV2(moco_dict_path)

    # Manually add tables to the dictionaries for testing
    # Add a table to coco_dict (subnode 0)
    dict_with_tables = DictionaryFactory.create_dictionary(
        tests.resources.TEST_DICTIONARY_WITH_TABLES_FOR_ALL_COM_TYPES, Interface.ETH
    )
    if 0 not in coco_dict._tables:
        coco_dict._tables[0] = {}
    coco_dict._tables[0]["TEST_TABLE_COCO"] = dict_with_tables._tables[0]["MEM_USR_DATA"]

    # Add a table to moco_dict (subnode 1)
    if 1 not in moco_dict._tables:
        moco_dict._tables[1] = {}
    moco_dict._tables[1]["TEST_TABLE_MOCO"] = dict_with_tables._tables[1]["COGGING_COMP_TABLE"]

    # Verify both have tables
    assert "TEST_TABLE_COCO" in coco_dict._tables[0]
    assert "TEST_TABLE_MOCO" in moco_dict._tables[1]

    # Merge dictionaries using + operator
    merged_dict = coco_dict + moco_dict

    # Verify both tables are present in merged dictionary
    assert "TEST_TABLE_COCO" in merged_dict._tables[0]
    assert "TEST_TABLE_MOCO" in merged_dict._tables[1]

    # Verify the tables are deep copies (not the same objects)
    assert id(coco_dict._tables[0]["TEST_TABLE_COCO"]) != id(
        merged_dict._tables[0]["TEST_TABLE_COCO"]
    )
    assert id(moco_dict._tables[1]["TEST_TABLE_MOCO"]) != id(
        merged_dict._tables[1]["TEST_TABLE_MOCO"]
    )


def test_merge_dictionaries_new_instance():
    coco_dict_path = tests.resources.comkit.COM_KIT_DICT
    moco_dict_path = tests.resources.comkit.CORE_DICT
    dict_a = EthernetDictionaryV2(coco_dict_path)
    dict_b = EthernetDictionaryV2(moco_dict_path)
    dict_c = dict_a + dict_b

    assert id(dict_c) != id(dict_a)
    assert id(dict_c) != id(dict_b)

    dict_d = dict_b + dict_a

    assert id(dict_d) != id(dict_a)
    assert id(dict_d) != id(dict_b)

    # The registers should reference different objects
    dict_a_reg_subnode_0 = dict_a.registers(0)["DRV_AXIS_NUMBER"]
    dict_b_reg_subnode_1 = dict_b.registers(1)["DRV_STATE_STATUS"]
    dict_c_reg_subnode_0 = dict_c.registers(0)["DRV_AXIS_NUMBER"]
    dict_c_reg_subnode_1 = dict_c.registers(1)["DRV_STATE_STATUS"]
    assert id(dict_a_reg_subnode_0) != id(dict_c_reg_subnode_0)
    assert id(dict_b_reg_subnode_1) != id(dict_c_reg_subnode_1)

    # Enum attributes should have the same reference
    assert id(dict_a.interface) == id(dict_c.interface)
    assert id(dict_b.interface) == id(dict_c.interface)


def test_merge_dictionaries_order_invariant():
    coco_dict_path = tests.resources.comkit.COM_KIT_DICT
    moco_dict_path = tests.resources.comkit.CORE_DICT
    dict_a = EthernetDictionaryV2(coco_dict_path) + EthernetDictionaryV2(moco_dict_path)
    dict_b = EthernetDictionaryV2(moco_dict_path) + EthernetDictionaryV2(coco_dict_path)
    assert dict_a.registers(0).keys() == dict_b.registers(0).keys()
    assert dict_a.registers(1).keys() == dict_b.registers(1).keys()
    assert dict_a.errors == dict_b.errors
    assert dict_a.product_code == dict_b.product_code
    assert dict_a.revision_number == dict_b.revision_number
    assert dict_a.firmware_version == dict_b.firmware_version
    assert dict_a.part_number == dict_b.part_number
    assert dict_a.image == dict_b.image
    assert dict_a.coco_product_code == dict_b.coco_product_code


def test_merge_dictionaries_type_exception():
    eth_v2_path = tests.resources.comkit.COM_KIT_DICT
    can_v2_path = tests.resources.canopen.TEST_DICT_CAN
    eth_v2_dict = EthernetDictionaryV2(eth_v2_path)
    can_v2_dict = CanopenDictionaryV2(can_v2_path)
    with pytest.raises(TypeError) as exc_info:
        eth_v2_dict + can_v2_dict
    assert (
        str(exc_info.value) == "Cannot merge dictionaries. Expected type: <class"
        " 'ingenialink.ethernet.dictionary.EthernetDictionaryV2'>, got: <class"
        " 'ingenialink.canopen.dictionary.CanopenDictionaryV2'>"
    )


def test_merge_dictionaries_no_coco_exception():
    moco_dict_path = tests.resources.comkit.CORE_DICT
    moco_a_dict = EthernetDictionaryV2(moco_dict_path)
    moco_b_dict = EthernetDictionaryV2(moco_dict_path)
    with pytest.raises(ValueError) as exc_info:
        moco_a_dict + moco_b_dict
    assert (
        str(exc_info.value)
        == "Cannot merge dictionaries. One of the dictionaries must be a COM-KIT dictionary."
    )


@pytest.mark.parametrize(
    "xml_attribute, class_attribute",
    [
        ("firmwareVersion", "firmware_version"),
        ("ProductCode", "product_code"),
        ("RevisionNumber", "revision_number"),
        ("PartNumber", "part_number"),
    ],
)
def test_dictionary_no_product_code(xml_attribute, class_attribute):
    with open(virtual_drive.resources.VIRTUAL_DRIVE_V2_XDF, encoding="utf-8") as xdf_file:
        tree = ElementTree.parse(xdf_file)
    root = tree.getroot()
    device = root.find(DictionaryV2._DictionaryV2__DICT_ROOT_DEVICE)
    device.attrib.pop(xml_attribute)
    xml_str = minidom.parseString(ElementTree.tostring(root)).toprettyxml(
        indent="  ", newl="", encoding="UTF-8"
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_file = join_path(tmp_dir, "temp.xdf")
        with open(temp_file, "wb") as merged_file:
            merged_file.write(xml_str)
        dictionary = EthernetDictionaryV2(temp_file)
    assert getattr(dictionary, class_attribute) is None


def test_get_register():
    dict_path = tests.resources.ethercat.TEST_DICT_ETHERCAT_AXIS
    dictionary = DictionaryFactory.create_dictionary(dict_path, Interface.ECAT)

    # Specify a uid that does not exist
    uid = "TEST_UID"
    with pytest.raises(ValueError, match=f"Register {uid} not found."):
        dictionary.get_register(uid=uid, axis=None)
    # Specify a uid and axis that does not exist
    with pytest.raises(KeyError, match="axis=3 does not exist."):
        dictionary.get_register(uid=uid, axis=3)

    # Register present in two axis, no axis specified
    uid = "DRV_DIAG_ERROR_LAST"
    with pytest.raises(
        ValueError, match=f"Register {uid} found in multiple axis. Axis should be specified."
    ):
        dictionary.get_register(uid=uid, axis=None)

    # Specify axis, but register does not exist in that axis
    with pytest.raises(KeyError, match=f"Register {uid} not present in axis=0"):
        dictionary.get_register(uid=uid, axis=0)

    # Find same uid in two different axis
    register_axis1 = dictionary.get_register(uid=uid, axis=1)
    assert register_axis1.subnode == 1
    register_axis2 = dictionary.get_register(uid=uid, axis=2)
    assert register_axis2.subnode == 2
    assert register_axis1.identifier == register_axis2.identifier

    # Specify a unique uid without providing the axis
    uid = "DRV_DIAG_ERROR_LAST_COM"
    register_1 = dictionary.get_register(uid=uid, axis=None)
    assert register_1.subnode == 0
    assert register_1.identifier == uid
    # Specify the same uid, providing the subnode, registers should match
    register_2 = dictionary.get_register(uid=uid, axis=0)
    assert register_1 == register_2


@pytest.mark.parametrize(
    "dictionary_path, interface",
    [
        (tests.resources.ethernet.TEST_DICT_ETHERNET_AXIS, Interface.ETH),
        (tests.resources.canopen.TEST_DICT_CAN_AXIS, Interface.CAN),
        (tests.resources.ethercat.TEST_DICT_ETHERCAT_AXIS, Interface.ECAT),
    ],
)
def test_register_description(dictionary_path, interface):
    expected_description_per_subnode = {
        0: {
            "DRV_DIAG_ERROR_LAST_COM": "Contains the last generated error",
            "DIST_CFG_REG0_MAP": "This register allows configuring the "
            "disturbance mapped register 0.",
        },
        1: {
            "DRV_DIAG_ERROR_LAST": "Contains the last generated error",
            "DRV_OP_CMD": "User requested mode of operation",
        },
        2: {
            "DRV_DIAG_ERROR_LAST": "Contains the last generated error",
            "DRV_STATE_CONTROL": "Parameter to manage the drive state machine. "
            "It is compliant with DS402.",
        },
    }
    dictionary_v2 = DictionaryFactory.create_dictionary(dictionary_path, interface)
    checked_registers = 0
    for subnode, registers in dictionary_v2._registers.items():
        for register in registers.values():
            if register.identifier not in expected_description_per_subnode[subnode]:
                continue
            assert (
                register.description
                == expected_description_per_subnode[subnode][register.identifier]
            )
            checked_registers += 1
    assert checked_registers == sum(
        len(subnode_registers) for subnode_registers in expected_description_per_subnode.values()
    )


def test_canopen_dictionary_get_register_by_index_subindex():
    dict_path = tests.resources.canopen.TEST_DICT_CAN_V3
    dictionary = DictionaryFactory.create_dictionary(dict_path, Interface.CAN)

    idx = 0x2010
    subidx = 0x0
    register = dictionary.get_register_by_index_subindex(idx, subidx)
    assert register.idx == idx
    assert register.subidx == subidx


def test_canopen_object_writable_registers():
    obj = CanOpenObject(
        uid="MON_DATA_VALUE",
        idx=0x58B2,
        object_type=CanOpenObjectType.RECORD,
        registers=[
            CanopenRegister(
                identifier="RANDOM_REG_1",
                idx=0x58B2,
                subidx=0x00,
                dtype=RegDtype.BYTE_ARRAY_512,
                access=RegAccess.RW,
            ),
            CanopenRegister(
                identifier="RANDOM_REG_2",
                idx=0x58B4,
                subidx=0x00,
                dtype=RegDtype.BYTE_ARRAY_512,
                access=RegAccess.WO,
            ),
        ],
    )
    assert obj.all_registers_writable is True

    # Change one register to RO, object should not be writable anymore
    obj = CanOpenObject(
        uid="MON_DATA_VALUE",
        idx=0x58B2,
        object_type=CanOpenObjectType.RECORD,
        registers=[
            CanopenRegister(
                identifier="RANDOM_REG_1",
                idx=0x58B2,
                subidx=0x00,
                dtype=RegDtype.BYTE_ARRAY_512,
                access=RegAccess.RO,
            ),
            CanopenRegister(
                identifier="RANDOM_REG_2",
                idx=0x58B4,
                subidx=0x00,
                dtype=RegDtype.BYTE_ARRAY_512,
                access=RegAccess.WO,
            ),
        ],
    )
    assert obj.all_registers_writable is False


@pytest.mark.parametrize(
    "interface",
    [
        Interface.CAN,
        Interface.ETH,
        Interface.ECAT,
        Interface.EoE,
    ],
)
def test_parse_tables(interface):
    """Test that the dictionary with tables is parsed correctly."""

    dict_path = tests.resources.TEST_DICTIONARY_WITH_TABLES_FOR_ALL_COM_TYPES
    expected_tables = {
        0: {
            "MEM_USR_DATA": {
                "id": "MEM_USR_DATA",
                "axis": None,
                "id_index": "MEM_USR_ADDR",
                "id_value": "MEM_USR_DATA",
            },
        },
        1: {
            "COGGING_COMP_TABLE": {
                "id": "COGGING_COMP_TABLE",
                "axis": 1,
                "id_index": "COGGING_COMP_TABLE_INDEX",
                "id_value": "COGGING_COMP_TABLE_VALUE",
            },
        },
    }
    dictionary = DictionaryFactory.create_dictionary(dict_path, interface)
    assert isinstance(dictionary._tables, dict)

    for axis, tables in expected_tables.items():
        axis_tables = dictionary._tables[axis]
        assert isinstance(axis_tables, dict)

        found_tables = {
            uid: {
                "id": table.id,
                "axis": table.axis,
                "id_index": table.id_index,
                "id_value": table.id_value,
            }
            for uid, table in axis_tables.items()
        }

        assert found_tables == tables


def test_get_table():
    """Test that get_table method works correctly."""
    dict_path = tests.resources.TEST_DICTIONARY_WITH_TABLES_FOR_ALL_COM_TYPES
    dictionary = DictionaryFactory.create_dictionary(dict_path, Interface.ETH)

    # Specify a uid that does not exist
    uid = "TEST_UID"
    with pytest.raises(ValueError, match=f"Table {uid} not found."):
        dictionary.get_table(uid=uid, axis=None)
    # Specify a uid and axis that does not exist
    with pytest.raises(KeyError, match="axis=3 does not exist."):
        dictionary.get_table(uid=uid, axis=3)

    # Table present in only one axis (axis 1), no axis specified - should succeed
    uid = "COGGING_COMP_TABLE"
    table = dictionary.get_table(uid=uid, axis=None)
    assert table.id == uid
    assert table.axis == 1
    assert table.id_index == "COGGING_COMP_TABLE_INDEX"
    assert table.id_value == "COGGING_COMP_TABLE_VALUE"

    # Specify axis explicitly
    table_axis1 = dictionary.get_table(uid=uid, axis=1)
    assert table_axis1.id == uid
    assert table_axis1.axis == 1

    # Specify wrong axis for this table
    with pytest.raises(KeyError, match=f"Table {uid} not present in axis=0"):
        dictionary.get_table(uid=uid, axis=0)

    # Specify a unique uid without providing the axis (axis 0)
    uid = "MEM_USR_DATA"
    table_1 = dictionary.get_table(uid=uid, axis=None)
    assert table_1.axis is None
    assert table_1.id == uid
    assert table_1.id_index == "MEM_USR_ADDR"
    assert table_1.id_value == "MEM_USR_DATA"
    # Specify the same uid, providing the axis, tables should match
    table_2 = dictionary.get_table(uid=uid, axis=0)
    assert table_1 == table_2
