import pytest

import tests.resources
from ingenialink.virtual.dictionary import VirtualDictionaryV2


def test_read_xdf_register_ethernet():
    dictionary_path = tests.resources.ethernet.TEST_DICT_ETHERNET
    address = 0x000F
    reg_id = "DRV_DIAG_ERROR_LAST_COM"
    subnode = 0

    ethernet_dict = VirtualDictionaryV2(dictionary_path)

    assert ethernet_dict.registers(subnode)[reg_id].address == address


@pytest.mark.parametrize(
    "reg_id,subnode,address",
    [("DRV_DIAG_ERROR_LAST_COM", 0, 0xF), ("COMMU_ANGLE_SENSOR", 1, 0x151)],
)
def test_read_xdf_register_canopen(reg_id, subnode, address):
    dictionary_path = tests.resources.canopen.TEST_DICT_CAN

    ethernet_dict = VirtualDictionaryV2(dictionary_path)

    assert ethernet_dict.registers(subnode)[reg_id].address == address


def test_no_cia_registers_in_dictionary():
    dictionary_path = tests.resources.canopen.TEST_DICT_CAN

    virtual_dict = VirtualDictionaryV2(dictionary_path)

    assert "CIA402" not in virtual_dict.categories.category_ids

    for subnode in virtual_dict.subnodes:
        for register in virtual_dict.registers(subnode):
            assert not register.startswith("CIA")
