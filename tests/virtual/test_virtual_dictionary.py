import pytest

import tests.resources
from ingenialink.virtual.dictionary import VirtualDictionary


@pytest.mark.no_connection
def test_read_xdf_register_ethernet():
    dictionary_path = tests.resources.ethernet.TEST_DICT_ETHERNET
    address = 0x000F
    reg_id = "DRV_DIAG_ERROR_LAST_COM"
    subnode = 0

    ethernet_dict = VirtualDictionary(dictionary_path)

    assert ethernet_dict.registers(subnode)[reg_id].address == address


@pytest.mark.parametrize(
    "reg_id,subnode,address",
    [("DRV_DIAG_ERROR_LAST_COM", 0, 0xF), ("COMMU_ANGLE_SENSOR", 1, 0x151)],
)
@pytest.mark.no_connection
def test_read_xdf_register_canopen(reg_id, subnode, address):
    dictionary_path = tests.resources.canopen.TEST_DICT_CAN

    ethernet_dict = VirtualDictionary(dictionary_path)

    assert ethernet_dict.registers(subnode)[reg_id].address == address
