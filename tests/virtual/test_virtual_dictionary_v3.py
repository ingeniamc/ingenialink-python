import pytest

from ingenialink.dictionary import Interface, SubnodeType
from ingenialink.ethernet.dictionary import EthernetDictionaryV3
from virtual_drive import resources as virtual_drive_resources

SINGLE_AXIS_SUBNODES = {
    0: SubnodeType.COMMUNICATION,
    1: SubnodeType.MOTION,
}


@pytest.mark.no_connection
def test_read_dictionary():
    expected_device_attr = {
        "path": virtual_drive_resources.VIRTUAL_DRIVE_V3_XDF,
        "version": "3.0",
        "firmware_version": "0.1.0",
        "product_code": 000000,
        "part_number": "VIRTUAL-DRIVE",
        "revision_number": 000000,
        "interface": Interface.ETH,
        "subnodes": SINGLE_AXIS_SUBNODES,
        "is_safe": False,
        "image": "image-text",
    }

    virtual_dict = EthernetDictionaryV3(virtual_drive_resources.VIRTUAL_DRIVE_V3_XDF)

    for attr, value in expected_device_attr.items():
        assert getattr(virtual_dict, attr) == value


@pytest.mark.no_connection
def test_read_dictionary_file_not_found():
    dictionary_path = "false.xdf"

    with pytest.raises(FileNotFoundError):
        EthernetDictionaryV3(dictionary_path, Interface.ETH)
