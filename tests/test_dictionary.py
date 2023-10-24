import io
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom

import pytest
from os.path import join as join_path

from ingenialink.canopen.dictionary import CanopenDictionary
from ingenialink.ethernet.dictionary import EthernetDictionary


path_resources = "./tests/resources/"


@pytest.mark.parametrize("dictionary_class", [CanopenDictionary, EthernetDictionary])
@pytest.mark.no_connection
def test_dictionary_image(dictionary_class):
    dictionary_path = join_path(path_resources, "virtual_drive.xdf")
    dictionary = dictionary_class(dictionary_path)
    image = dictionary.image
    assert isinstance(image, str)


@pytest.mark.parametrize("dictionary_class", [CanopenDictionary, EthernetDictionary])
@pytest.mark.no_connection
def test_dictionary_image_none(dictionary_class):
    dictionary_path = join_path(path_resources, "virtual_drive.xdf")
    with open(dictionary_path, "r", encoding="utf-8") as xdf_file:
        tree = ET.parse(xdf_file)
    root = tree.getroot()
    root.remove(root.find(dictionary_class.DICT_IMAGE))
    xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(
        indent="  ", newl="", encoding="UTF-8"
    )
    temp_file = join_path(path_resources, "temp.xdf")
    merged_file = io.open(temp_file, "wb")
    merged_file.write(xml_str)
    merged_file.close()
    dictionary = dictionary_class(temp_file)
    os.remove(temp_file)
    image = dictionary.image
    assert image is None
