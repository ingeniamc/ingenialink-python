from os.path import join as join_path

import pytest

from ingenialink.canopen.dictionary import CanopenDictionaryV2
from ingenialink.dictionary import Interface, SubnodeType

path_resources = "./tests/resources/canopen/"
SINGLE_AXIS_BASE_SUBNODES = {0: SubnodeType.COMMUNICATION, 1: SubnodeType.MOTION}


@pytest.mark.no_connection
def test_read_dictionary():
    dictionary_path = join_path(path_resources, "test_dict_can.xdf")
    expected_device_attr = {
        "path": dictionary_path,
        "version": "2",
        "firmware_version": "2.0.1",
        "product_code": 57745409,
        "part_number": "CAP-NET-C",
        "revision_number": 196635,
        "interface": Interface.CAN,
        "subnodes": SINGLE_AXIS_BASE_SUBNODES,
        "is_safe": False,
    }

    canopen_dict = CanopenDictionaryV2(dictionary_path)

    for attr, value in expected_device_attr.items():
        assert getattr(canopen_dict, attr) == value


@pytest.mark.no_connection
def test_read_dictionary_file_not_found():
    dictionary_path = "false.xdf"

    with pytest.raises(FileNotFoundError):
        CanopenDictionaryV2(dictionary_path)


@pytest.mark.no_connection
def test_read_dictionary_registers():
    dictionary_path = join_path(path_resources, "test_dict_can.xdf")
    expected_regs_per_subnode = {
        0: [
            "DRV_DIAG_ERROR_LAST_COM",
            "DIST_CFG_REG0_MAP",
            "DRV_AXIS_NUMBER",
            "COMMS_ETH_IP",
            "COMMS_ETH_NET_MASK",
        ],
        1: ["COMMU_ANGLE_SENSOR"],
    }

    canopen_dict = CanopenDictionaryV2(dictionary_path)

    for subnode in expected_regs_per_subnode:
        assert expected_regs_per_subnode[subnode] == list(canopen_dict.registers(subnode))


@pytest.mark.no_connection
def test_read_dictionary_registers_multiaxis():
    expected_num_registers_per_subnode = {0: 6, 1: 5, 2: 5}
    dictionary_path = join_path(path_resources, "test_dict_can_axis.xdf")

    canopen_dict = CanopenDictionaryV2(dictionary_path)
    assert canopen_dict.subnodes == {
        0: SubnodeType.COMMUNICATION,
        1: SubnodeType.MOTION,
        2: SubnodeType.MOTION,
    }
    for subnode in expected_num_registers_per_subnode:
        num_registers = len(canopen_dict.registers(subnode))
        assert num_registers == expected_num_registers_per_subnode[subnode]


@pytest.mark.no_connection
def test_read_dictionary_registers_attr_errors():
    dictionary_path = join_path(path_resources, "test_dict_can_no_attr_reg.xdf")

    canopen_dict = CanopenDictionaryV2(dictionary_path)

    for subnode in range(2):
        num_registers = len(canopen_dict.registers(subnode))
        assert num_registers == 0


@pytest.mark.no_connection
def test_read_dictionary_categories():
    expected_categories = [
        "IDENTIFICATION",
        "COMMUNICATIONS",
        "COMMUTATION",
        "REPORTING",
        "MONITORING",
    ]
    dictionary_path = join_path(path_resources, "test_dict_can.xdf")

    canopen_dict = CanopenDictionaryV2(dictionary_path)

    assert canopen_dict.categories.category_ids == expected_categories


@pytest.mark.no_connection
def test_read_dictionary_errors():
    expected_errors = [
        0x00003280,
        0x00007380,
        0x00007385,
        0x06010000,
    ]
    dictionary_path = join_path(path_resources, "test_dict_can.xdf")

    canopen_dict = CanopenDictionaryV2(dictionary_path)

    assert list(canopen_dict.errors) == expected_errors


@pytest.mark.no_connection
def test_read_xdf_register():
    dictionary_path = join_path(path_resources, "test_dict_can.xdf")
    idx = 0x580F
    subidx = 0x00
    reg_id = "DRV_DIAG_ERROR_LAST_COM"
    subnode = 0

    canopen_dict = CanopenDictionaryV2(dictionary_path)

    assert canopen_dict.registers(subnode)[reg_id].idx == idx
    assert canopen_dict.registers(subnode)[reg_id].subidx == subidx


@pytest.mark.no_connection
def test_object_not_exist():
    dictionary_path = join_path(path_resources, "test_dict_can.xdf")
    canopen_dict = CanopenDictionaryV2(dictionary_path)
    with pytest.raises(KeyError):
        canopen_dict.get_object("NOT_EXISTING_UID", 0)


@pytest.mark.no_connection
def test_safety_pdo_not_implemented():
    dictionary_path = join_path(path_resources, "test_dict_can.xdf")
    canopen_dict = CanopenDictionaryV2(dictionary_path)
    with pytest.raises(NotImplementedError):
        canopen_dict.get_safety_rpdo("NOT_EXISTING_UID")
    with pytest.raises(NotImplementedError):
        canopen_dict.get_safety_tpdo("NOT_EXISTING_UID")
