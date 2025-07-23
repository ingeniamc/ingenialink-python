import pytest

import tests.resources.ethernet
from ingenialink.dictionary import Interface, SubnodeType
from ingenialink.ethernet.dictionary import EthernetDictionaryV2

SINGLE_AXIS_BASE_SUBNODES = {0: SubnodeType.COMMUNICATION, 1: SubnodeType.MOTION}


@pytest.mark.no_connection
def test_read_dictionary():
    dictionary_path = tests.resources.ethernet.TEST_DICT_ETHERNET
    expected_device_attr = {
        "path": dictionary_path,
        "version": "2",
        "firmware_version": "2.0.1",
        "product_code": 57745409,
        "part_number": "CAP-NET-C",
        "revision_number": 196635,
        "interface": Interface.ETH,
        "subnodes": SINGLE_AXIS_BASE_SUBNODES,
    }

    ethernet_dict = EthernetDictionaryV2(dictionary_path)

    for attr, value in expected_device_attr.items():
        assert getattr(ethernet_dict, attr) == value


@pytest.mark.no_connection
def test_read_dictionary_file_not_found():
    dictionary_path = "false.xdf"

    with pytest.raises(FileNotFoundError):
        EthernetDictionaryV2(dictionary_path)


@pytest.mark.no_connection
def test_read_dictionary_registers():
    dictionary_path = tests.resources.ethernet.TEST_DICT_ETHERNET
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

    ethernet_dict = EthernetDictionaryV2(dictionary_path)

    for subnode in expected_regs_per_subnode:
        assert expected_regs_per_subnode[subnode] == list(ethernet_dict.registers(subnode))


@pytest.mark.no_connection
def test_read_dictionary_registers_multiaxis():
    expected_num_registers_per_subnode = {0: 2, 1: 2, 2: 2}
    dictionary_path = tests.resources.ethernet.TEST_DICT_ETHERNET_AXIS

    ethernet_dict = EthernetDictionaryV2(dictionary_path)
    assert ethernet_dict.subnodes == {
        0: SubnodeType.COMMUNICATION,
        1: SubnodeType.MOTION,
        2: SubnodeType.MOTION,
    }

    for subnode in expected_num_registers_per_subnode:
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
    dictionary_path = tests.resources.ethernet.TEST_DICT_ETHERNET

    ethernet_dict = EthernetDictionaryV2(dictionary_path)

    assert ethernet_dict.categories.category_ids == expected_categories


@pytest.mark.no_connection
def test_read_dictionary_errors():
    expected_errors = [
        0x00003280,
        0x00007380,
        0x00007385,
        0x06010000,
    ]
    dictionary_path = tests.resources.ethernet.TEST_DICT_ETHERNET

    ethernet_dict = EthernetDictionaryV2(dictionary_path)

    assert list(ethernet_dict.errors) == expected_errors


@pytest.mark.no_connection
def test_read_xdf_register():
    dictionary_path = tests.resources.ethernet.TEST_DICT_ETHERNET
    address = 0x000F
    reg_id = "DRV_DIAG_ERROR_LAST_COM"
    subnode = 0

    ethernet_dict = EthernetDictionaryV2(dictionary_path)

    assert ethernet_dict.registers(subnode)[reg_id].address == address


@pytest.mark.no_connection
def test_object_not_exist():
    dictionary_path = tests.resources.ethernet.TEST_DICT_ETHERNET
    ethernet_dict = EthernetDictionaryV2(dictionary_path)
    with pytest.raises(KeyError):
        ethernet_dict.get_object("NOT_EXISTING_UID", 0)


@pytest.mark.no_connection
def test_safety_pdo_not_implemented():
    dictionary_path = tests.resources.ethernet.TEST_DICT_ETHERNET
    ethernet_dict = EthernetDictionaryV2(dictionary_path)
    with pytest.raises(NotImplementedError):
        ethernet_dict.get_safety_rpdo("NOT_EXISTING_UID")
    with pytest.raises(NotImplementedError):
        ethernet_dict.get_safety_tpdo("NOT_EXISTING_UID")
