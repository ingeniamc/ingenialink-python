from os.path import join as join_path

import pytest

from ingenialink.virtual.dictionary import VirtualDictionary

path_resources = "./tests/resources/"


@pytest.mark.no_connection
def test_read_xdf_register_ethernet():
    dictionary_path = join_path(path_resources, "ethernet/test_dict_eth.xdf")
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
    dictionary_path = join_path(path_resources, "canopen/test_dict_can.xdf")

    ethernet_dict = VirtualDictionary(dictionary_path)

    assert ethernet_dict.registers(subnode)[reg_id].address == address
