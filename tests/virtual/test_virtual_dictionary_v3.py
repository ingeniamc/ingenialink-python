from pathlib import Path

import pytest

from ingenialink.dictionary import DictionaryV3, Interface, SubnodeType

SINGLE_AXIS_SUBNODES = {
    0: SubnodeType.COMMUNICATION,
    1: SubnodeType.MOTION,
}


@pytest.fixture(scope="session")
def virtual_dictionary_v3(virtual_drive_resources_folder: str) -> Path:
    return Path(virtual_drive_resources_folder) / "virtual_drive_v3.0.xdf"


@pytest.mark.no_connection
def test_read_dictionary(virtual_dictionary_v3):
    expected_device_attr = {
        "path": virtual_dictionary_v3.as_posix(),
        "version": "3.0",
        "firmware_version": "0.1.0",
        "product_code": 000000,
        "part_number": "VIRTUAL-DRIVE",
        "revision_number": 000000,
        "interface": Interface.ECAT,
        "subnodes": SINGLE_AXIS_SUBNODES,
        "is_safe": False,
        "image": "image-text",
    }

    virtual_dict = DictionaryV3(virtual_dictionary_v3.as_posix(), Interface.ETH)

    for attr, value in expected_device_attr.items():
        assert getattr(virtual_dict, attr) == value
