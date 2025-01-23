from os.path import join as join_path

import pytest

from ingenialink.dictionary import Interface, SubnodeType
from ingenialink.ethercat.dictionary import EthercatDictionaryV2

path_resources = "./tests/resources/ethercat/"
SINGLE_AXIS_BASE_SUBNODES = {0: SubnodeType.COMMUNICATION, 1: SubnodeType.MOTION}


@pytest.mark.no_connection
def test_read_dictionary():
    dictionary_path = join_path(path_resources, "test_dict_ethercat.xdf")
    expected_device_attr = {
        "path": dictionary_path,
        "version": "2",
        "firmware_version": "2.0.1",
        "product_code": 57745409,
        "part_number": "CAP-NET-E",
        "revision_number": 196635,
        "interface": Interface.ECAT,
        "subnodes": SINGLE_AXIS_BASE_SUBNODES,
        "is_safe": False,
    }

    ethercat_dict = EthercatDictionaryV2(dictionary_path)

    for attr, value in expected_device_attr.items():
        assert getattr(ethercat_dict, attr) == value


@pytest.mark.no_connection
def test_read_dictionary_file_not_found():
    dictionary_path = "false.xdf"

    with pytest.raises(FileNotFoundError):
        EthercatDictionaryV2(dictionary_path)


@pytest.mark.no_connection
def test_read_dictionary_registers():
    dictionary_path = join_path(path_resources, "test_dict_ethercat.xdf")
    expected_regs_per_subnode = {
        0: [
            "DRV_DIAG_ERROR_LAST_COM",
            "DIST_CFG_REG0_MAP",
            "COMMS_ETH_IP",
            "COMMS_ETH_NET_MASK",
            "DRV_BOOT_COCO_VERSION",
            "MON_CFG_EOC_TYPE",
            "RPDO_ASSIGN_REGISTER_SUB_IDX_0",
            "RPDO_ASSIGN_REGISTER_SUB_IDX_1",
            "RPDO_MAP_REGISTER_SUB_IDX_0",
            "RPDO_MAP_REGISTER_SUB_IDX_1",
            "TPDO_ASSIGN_REGISTER_SUB_IDX_0",
            "TPDO_ASSIGN_REGISTER_SUB_IDX_1",
            "TPDO_MAP_REGISTER_SUB_IDX_0",
            "TPDO_MAP_REGISTER_SUB_IDX_1",
        ],
        1: [
            "CL_POS_SET_POINT_VALUE",
            "CL_POS_FBK_VALUE",
            "CL_VEL_SET_POINT_VALUE",
            "CL_VEL_FBK_VALUE",
            "COMMU_ANGLE_SENSOR",
        ],
    }

    ethercat_dict = EthercatDictionaryV2(dictionary_path)

    for subnode in expected_regs_per_subnode:
        assert expected_regs_per_subnode[subnode] == [
            reg for reg in ethercat_dict.registers(subnode)
        ]


@pytest.mark.no_connection
def test_read_dictionary_registers_multiaxis():
    expected_num_registers_per_subnode = {0: 10, 1: 2, 2: 2}
    dictionary_path = join_path(path_resources, "test_dict_ethercat_axis.xdf")

    ethercat_dict = EthercatDictionaryV2(dictionary_path)
    assert ethercat_dict.subnodes == {
        0: SubnodeType.COMMUNICATION,
        1: SubnodeType.MOTION,
        2: SubnodeType.MOTION,
    }

    for subnode in expected_num_registers_per_subnode:
        num_registers = len(ethercat_dict.registers(subnode))
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
    dictionary_path = join_path(path_resources, "test_dict_ethercat.xdf")

    ethercat_dict = EthercatDictionaryV2(dictionary_path)

    assert ethercat_dict.categories.category_ids == expected_categories


@pytest.mark.no_connection
def test_read_dictionary_errors():
    expected_errors = [
        0x00003280,
        0x00007380,
        0x00007385,
        0x06010000,
    ]
    dictionary_path = join_path(path_resources, "test_dict_ethercat.xdf")

    ethercat_dict = EthercatDictionaryV2(dictionary_path)

    assert [error for error in ethercat_dict.errors] == expected_errors


@pytest.mark.no_connection
def test_read_xdf_register():
    dictionary_path = join_path(path_resources, "test_dict_ethercat.xdf")
    idx = 0x580F
    subidx = 0x00
    reg_id = "DRV_DIAG_ERROR_LAST_COM"
    subnode = 0

    ethercat_dict = EthercatDictionaryV2(dictionary_path)

    assert ethercat_dict.registers(subnode)[reg_id].idx == idx
    assert ethercat_dict.registers(subnode)[reg_id].subidx == subidx


@pytest.mark.no_connection
@pytest.mark.parametrize(
    "register_uid, subnode, idx",
    [("DIST_CFG_REG0_MAP", 0, 0x5890), ("DRV_OP_CMD", 1, 0x2014), ("DRV_STATE_CONTROL", 2, 0x2810)],
)
def test_mcb_to_can_mapping(register_uid, subnode, idx):
    dictionary_path = join_path(path_resources, "test_dict_ethercat_axis.xdf")

    ethercat_dict = EthercatDictionaryV2(dictionary_path)

    ethercat_register = ethercat_dict.registers(subnode)[register_uid]
    assert ethercat_register.idx == idx


@pytest.mark.no_connection
def test_child_registers_not_exist():
    dictionary_path = join_path(path_resources, "test_dict_ethercat.xdf")
    ethercat_dict = EthercatDictionaryV2(dictionary_path)
    with pytest.raises(KeyError):
        ethercat_dict.child_registers("NOT_EXISTING_UID", 0)


@pytest.mark.no_connection
def test_safety_pdo_not_implemented():
    dictionary_path = join_path(path_resources, "test_dict_ethercat.xdf")
    ethercat_dict = EthercatDictionaryV2(dictionary_path)
    with pytest.raises(NotImplementedError):
        ethercat_dict.get_safety_rpdo("NOT_EXISTING_UID")
    with pytest.raises(NotImplementedError):
        ethercat_dict.get_safety_tpdo("NOT_EXISTING_UID")
