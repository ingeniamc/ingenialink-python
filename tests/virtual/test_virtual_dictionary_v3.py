import pytest
from virtual_drive import resources as virtual_drive_resources

import tests.resources
from ingenialink.dictionary import Interface, SubnodeType
from ingenialink.virtual.dictionary import VirtualDictionaryV3

SINGLE_AXIS_SUBNODES = {
    0: SubnodeType.COMMUNICATION,
    1: SubnodeType.MOTION,
}


@pytest.mark.parametrize(
    "dictionary_path, expected_device_attr",
    [
        (
            virtual_drive_resources.VIRTUAL_DRIVE_V3_XDF,
            {
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
            },
        ),
        (
            tests.resources.TEST_DICT_ECAT_EOE_v3,
            {
                "path": tests.resources.TEST_DICT_ECAT_EOE_v3,
                "version": "3.0",
                "firmware_version": "2.4.1",
                "product_code": 61939713,
                "part_number": "EVS-NET-E",
                "revision_number": 196617,
                "interface": Interface.EoE,
                "subnodes": SINGLE_AXIS_SUBNODES,
                "is_safe": False,
                "image": "image-text",
            },
        ),
        (
            tests.resources.canopen.TEST_DICT_CAN_V3,
            {
                "path": tests.resources.canopen.TEST_DICT_CAN_V3,
                "version": "3.0",
                "firmware_version": "2.4.1",
                "product_code": 61939713,
                "part_number": "EVS-NET-C",
                "revision_number": 196617,
                "interface": Interface.ETH,
                "subnodes": SINGLE_AXIS_SUBNODES,
                "is_safe": False,
                "image": "image-text",
            },
        ),
    ],
)
def test_read_dictionary(dictionary_path, expected_device_attr):
    virtual_dict = VirtualDictionaryV3(dictionary_path)
    for attr, value in expected_device_attr.items():
        assert getattr(virtual_dict, attr) == value


def test_read_dictionary_file_not_found():
    dictionary_path = "false.xdf"

    with pytest.raises(FileNotFoundError):
        VirtualDictionaryV3(dictionary_path, Interface.ETH)
