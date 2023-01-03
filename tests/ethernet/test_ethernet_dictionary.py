import pytest
from os.path import join as join_path

from ingenialink.ethernet.dictionary import EthernetDictionary
from ingenialink.constants import SINGLE_AXIS_MINIMUM_SUBNODES


path_resources = "./tests/resources/ethernet/"


@pytest.mark.no_connection
def test_read_dictionary():
    dictionary_path = join_path(path_resources, "test_dict_eth.xdf")
    expected_device_attr = {
        "path": dictionary_path,
        "version": "2",
        "firmware_version": "2.0.1",
        "product_code": 57745409,
        "part_number": "CAP-NET-C",
        "revision_number": 196635,
        "interface": "ETH",
        "subnodes": SINGLE_AXIS_MINIMUM_SUBNODES,
    }

    ethernet_dict = EthernetDictionary(dictionary_path)

    for attr, value in expected_device_attr.items():
        assert getattr(ethernet_dict, attr) == value


@pytest.mark.no_connection
def test_read_dictionary_file_not_found():
    dictionary_path = "false.xdf"

    with pytest.raises(FileNotFoundError):
        EthernetDictionary(dictionary_path)


@pytest.mark.no_connection
def test_read_dictionary_registers():
    dictionary_path = join_path(path_resources, "test_dict_eth.xdf")
    expected_regs_per_subnode = {
        0: [
            "DRV_DIAG_ERROR_LAST_COM",
            "DIST_CFG_REG0_MAP",
            "COMMS_ETH_IP",
            "COMMS_ETH_NET_MASK",
            "DRV_BOOT_COCO_VERSION",
            "MON_CFG_EOC_TYPE",
        ]
    }

    ethernet_dict = EthernetDictionary(dictionary_path)

    for subnode in expected_regs_per_subnode.keys():
        assert expected_regs_per_subnode[subnode] == [
            reg for reg in ethernet_dict.registers(subnode)
        ]


@pytest.mark.no_connection
def test_read_dictionary_registers_multiaxis():
    expected_num_registers_per_subnode = {0: 2, 1: 2, 2: 2}
    dictionary_path = join_path(path_resources, "test_dict_eth_axis.xdf")

    ethernet_dict = EthernetDictionary(dictionary_path)

    for subnode in expected_num_registers_per_subnode.keys():
        num_registers = len(ethernet_dict.registers(subnode))
        assert num_registers == expected_num_registers_per_subnode[subnode]


@pytest.mark.no_connection
def test_read_dictionary_categories():
    expected_categories = [
        "IDENTIFICATION",
        "COMMUTATION",
        "COMMUNICATIONS",
        "REPORTING",
        "MONITORING",
    ]
    dictionary_path = join_path(path_resources, "test_dict_eth.xdf")

    ethernet_dict = EthernetDictionary(dictionary_path)

    assert ethernet_dict.categories.category_ids == expected_categories


@pytest.mark.no_connection
def test_read_dictionary_errors():
    expected_errors = [
        0x00003280,
        0x00007380,
        0x00007385,
        0x06010000,
    ]
    dictionary_path = join_path(path_resources, "test_dict_eth.xdf")

    ethernet_dict = EthernetDictionary(dictionary_path)

    assert [error for error in ethernet_dict.errors.errors] == expected_errors


@pytest.mark.no_connection
def test_read_xdf_register():
    dictionary_path = join_path(path_resources, "test_dict_eth.xdf")
    address = 0x000F
    reg_id = "DRV_DIAG_ERROR_LAST_COM"
    subnode = 0

    ethernet_dict = EthernetDictionary(dictionary_path)

    assert ethernet_dict.registers(subnode)[reg_id].address == address
