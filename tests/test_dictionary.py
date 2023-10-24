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
