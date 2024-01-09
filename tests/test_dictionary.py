import io
import os
import xml.etree.ElementTree as ET
from os.path import join as join_path
from xml.dom import minidom

import pytest

from ingenialink.canopen.dictionary import CanopenDictionary
from ingenialink.ethernet.dictionary import EthernetDictionary

PATH_RESOURCE = "./tests/resources/"
PATH_TO_DICTIONARY = "./ingenialink/virtual/resources/virtual_drive.xdf"


@pytest.mark.parametrize("dictionary_class", [CanopenDictionary, EthernetDictionary])
@pytest.mark.no_connection
def test_dictionary_image(dictionary_class):
    dictionary = dictionary_class(PATH_TO_DICTIONARY)
    assert isinstance(dictionary.image, str)
    assert dictionary.moco_image is None


@pytest.mark.parametrize("dictionary_class", [CanopenDictionary, EthernetDictionary])
@pytest.mark.no_connection
def test_dictionary_image_none(dictionary_class):
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


@pytest.mark.parametrize("dictionary_class", [CanopenDictionary, EthernetDictionary])
@pytest.mark.no_connection
def test_dictionary_moco_image(dictionary_class):
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
