import io
import os
import tempfile
import xml.etree.ElementTree as ET
from os.path import join as join_path
from xml.dom import minidom

import pytest

from ingenialink.canopen.dictionary import CanopenDictionaryV2
from ingenialink.dictionary import DictionaryV2, DictionaryV3, Interface
from ingenialink.ethercat.dictionary import EthercatDictionaryV2
from ingenialink.ethernet.dictionary import EthernetDictionaryV2
from ingenialink.servo import DictionaryFactory

PATH_RESOURCE = "./tests/resources/"
PATH_TO_DICTIONARY = "./virtual_drive/resources/virtual_drive.xdf"


@pytest.mark.parametrize("dictionary_class", [CanopenDictionaryV2, EthernetDictionaryV2])
@pytest.mark.no_connection
def test_dictionary_v2_image(dictionary_class):
    dictionary = dictionary_class(PATH_TO_DICTIONARY)
    assert isinstance(dictionary.image, str)


@pytest.mark.parametrize("dictionary_class", [CanopenDictionaryV2, EthernetDictionaryV2])
@pytest.mark.no_connection
def test_dictionary_v2_image_none(dictionary_class):
    with open(PATH_TO_DICTIONARY, "r", encoding="utf-8") as xdf_file:
        tree = ET.parse(xdf_file)
    root = tree.getroot()
    root.remove(root.find(DictionaryV2._DictionaryV2__DICT_IMAGE))
    xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(
        indent="  ", newl="", encoding="UTF-8"
    )
    temp_file = join_path(PATH_RESOURCE, "temp.xdf")
    merged_file = io.open(temp_file, "wb")
    merged_file.write(xml_str)
    merged_file.close()
    dictionary = dictionary_class(temp_file)
    os.remove(temp_file)
    assert dictionary.image is None


@pytest.mark.no_connection
@pytest.mark.parametrize(
    "dict_path, interface, dict_class",
    [
        (f"{PATH_RESOURCE}canopen/test_dict_can.xdf", Interface.CAN, CanopenDictionaryV2),
        (f"{PATH_RESOURCE}canopen/test_dict_can_v3.0.xdf", Interface.CAN, DictionaryV3),
        (f"{PATH_RESOURCE}ethercat/test_dict_ethercat.xdf", Interface.ECAT, EthercatDictionaryV2),
        (f"{PATH_RESOURCE}ethernet/test_dict_eth.xdf", Interface.ETH, EthernetDictionaryV2),
        (f"{PATH_RESOURCE}ethercat/test_dict_ethercat.xdf", Interface.EoE, EthernetDictionaryV2),
        (f"{PATH_RESOURCE}test_dict_ecat_eoe_v3.0.xdf", Interface.ECAT, DictionaryV3),
        (f"{PATH_RESOURCE}test_dict_ecat_eoe_v3.0.xdf", Interface.EoE, DictionaryV3),
    ],
)
def test_dictionary_factory(dict_path, interface, dict_class):
    test_dict = DictionaryFactory.create_dictionary(dict_path, interface)
    assert isinstance(test_dict, dict_class)


@pytest.mark.no_connection
def test_merge_dictionaries_registers():
    coco_dict_path = f"{PATH_RESOURCE}comkit/com-kit.xdf"
    moco_dict_path = f"{PATH_RESOURCE}comkit/core.xdf"
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


@pytest.mark.no_connection
def test_merge_dictionaries_errors():
    coco_dict_path = f"{PATH_RESOURCE}comkit/com-kit.xdf"
    moco_dict_path = f"{PATH_RESOURCE}comkit/core.xdf"
    coco_dict = EthernetDictionaryV2(coco_dict_path)
    moco_dict = EthernetDictionaryV2(moco_dict_path)
    coco_num_errors = len(coco_dict.errors)
    assert coco_num_errors == 1
    moco_num_errors = len(moco_dict.errors)
    assert moco_num_errors == 1
    merged_dict = coco_dict + moco_dict
    merged_dict_num_errors = len(merged_dict.errors)
    assert merged_dict_num_errors == coco_num_errors + moco_num_errors


@pytest.mark.no_connection
def test_merge_dictionaries_attributes():
    coco_dict_path = f"{PATH_RESOURCE}comkit/com-kit.xdf"
    moco_dict_path = f"{PATH_RESOURCE}comkit/core.xdf"
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


@pytest.mark.no_connection
def test_merge_dictionaries_image():
    coco_dict_path = f"{PATH_RESOURCE}comkit/com-kit.xdf"
    moco_dict_path = f"{PATH_RESOURCE}comkit/core.xdf"
    coco_dict = EthernetDictionaryV2(coco_dict_path)
    moco_dict = EthernetDictionaryV2(moco_dict_path)
    assert coco_dict.image is None
    assert isinstance(moco_dict.image, str)
    merged_dict = coco_dict + moco_dict
    assert merged_dict.image == moco_dict.image


@pytest.mark.no_connection
def test_merge_dictionaries_new_instance():
    coco_dict_path = f"{PATH_RESOURCE}comkit/com-kit.xdf"
    moco_dict_path = f"{PATH_RESOURCE}comkit/core.xdf"
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


@pytest.mark.no_connection
def test_merge_dictionaries_order_invariant():
    coco_dict_path = f"{PATH_RESOURCE}comkit/com-kit.xdf"
    moco_dict_path = f"{PATH_RESOURCE}comkit/core.xdf"
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


@pytest.mark.no_connection
def test_merge_dictionaries_type_exception():
    eth_v2_path = f"{PATH_RESOURCE}comkit/com-kit.xdf"
    can_v2_path = f"{PATH_RESOURCE}canopen/test_dict_can.xdf"
    eth_v2_dict = EthernetDictionaryV2(eth_v2_path)
    can_v2_dict = CanopenDictionaryV2(can_v2_path)
    with pytest.raises(TypeError) as exc_info:
        eth_v2_dict + can_v2_dict
    assert (
        str(exc_info.value) == "Cannot merge dictionaries. Expected type: <class"
        " 'ingenialink.ethernet.dictionary.EthernetDictionaryV2'>, got: <class"
        " 'ingenialink.canopen.dictionary.CanopenDictionaryV2'>"
    )


@pytest.mark.no_connection
def test_merge_dictionaries_no_coco_exception():
    moco_dict_path = f"{PATH_RESOURCE}comkit/core.xdf"
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
@pytest.mark.no_connection
def test_dictionary_no_product_code(xml_attribute, class_attribute):
    with open(PATH_TO_DICTIONARY, "r", encoding="utf-8") as xdf_file:
        tree = ET.parse(xdf_file)
    root = tree.getroot()
    device = root.find(DictionaryV2._DictionaryV2__DICT_ROOT_DEVICE)
    device.attrib.pop(xml_attribute)
    xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(
        indent="  ", newl="", encoding="UTF-8"
    )
    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_file = join_path(tmp_dir, "temp.xdf")
        with open(temp_file, "wb") as merged_file:
            merged_file.write(xml_str)
        dictionary = EthernetDictionaryV2(temp_file)
    assert getattr(dictionary, class_attribute) is None
