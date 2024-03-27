import io
import os
import xml.etree.ElementTree as ET
from os.path import join as join_path
from xml.dom import minidom

import pytest

from ingenialink.dictionary import Interface, DictionaryV3
from ingenialink.ethercat.dictionary import EthercatDictionaryV2
from ingenialink.ethernet.dictionary import EthernetDictionaryV2
from ingenialink.canopen.dictionary import CanopenDictionaryV2
from ingenialink.servo import DictionaryFactory

PATH_RESOURCE = "./tests/resources/"
PATH_TO_DICTIONARY = "./virtual_drive/resources/virtual_drive.xdf"


@pytest.mark.parametrize("dictionary_class", [CanopenDictionaryV2, EthernetDictionaryV2])
@pytest.mark.no_connection
def test_dictionary_v2_image(dictionary_class):
    dictionary = dictionary_class(PATH_TO_DICTIONARY)
    assert isinstance(dictionary.image, str)
    assert dictionary.moco_image is None


@pytest.mark.parametrize("dictionary_class", [CanopenDictionaryV2, EthernetDictionaryV2])
@pytest.mark.no_connection
def test_dictionary_v2_image_none(dictionary_class):
    with open(PATH_TO_DICTIONARY, "r", encoding="utf-8") as xdf_file:
        tree = ET.parse(xdf_file)
    root = tree.getroot()
    root.remove(root.find(dictionary_class.DICT_IMAGE))
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
    assert dictionary.moco_image is None


@pytest.mark.parametrize("dictionary_class", [CanopenDictionaryV2, EthernetDictionaryV2])
@pytest.mark.no_connection
def test_dictionary_v2_moco_image(dictionary_class):
    with open(PATH_TO_DICTIONARY, "r", encoding="utf-8") as xdf_file:
        tree = ET.parse(xdf_file)
    root = tree.getroot()
    image_section = root.find(dictionary_class.DICT_IMAGE)
    image_section.set("type", "moco")
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
    assert isinstance(dictionary.moco_image, str)


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
