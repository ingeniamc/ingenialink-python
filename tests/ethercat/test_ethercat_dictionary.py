import pytest
from os.path import join as join_path

from ingenialink.ethercat.dictionary import EthercatDictionary


path_resources = "./tests/resources/ethercat/"


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
        "interface": "ETH",
        "subnodes": 2,
    }

    ethercat_dict = EthercatDictionary(dictionary_path)

    for attr, value in expected_device_attr.items():
        assert getattr(ethercat_dict, attr) == value


@pytest.mark.no_connection
def test_read_dictionary_file_not_found():
    dictionary_path = "false.xdf"

    with pytest.raises(FileNotFoundError):
        EthercatDictionary(dictionary_path)


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
        ],
        1: ["COMMU_ANGLE_SENSOR"],
    }

    ethercat_dict = EthercatDictionary(dictionary_path)

    for subnode in expected_regs_per_subnode.keys():
        assert expected_regs_per_subnode[subnode] == [
            reg for reg in ethercat_dict.registers(subnode)
        ]


@pytest.mark.no_connection
def test_read_dictionary_registers_multiaxis():
    expected_num_registers_per_subnode = {0: 2, 1: 2, 2: 2}
    dictionary_path = join_path(path_resources, "test_dict_ethercat_axis.xdf")

    ethernet_dict = EthercatDictionary(dictionary_path)

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
    dictionary_path = join_path(path_resources, "test_dict_ethercat.xdf")

    ethernet_dict = EthercatDictionary(dictionary_path)

    assert ethernet_dict.categories.category_ids == expected_categories


@pytest.mark.no_connection
def test_read_dictionary_errors():
    expected_errors = [
        0x00003280,
        0x00007380,
        0x00007385,
        0x06010000,
    ]
    dictionary_path = join_path(path_resources, "test_dict_ethercat.xdf")

    ethercat_dict = EthercatDictionary(dictionary_path)

    assert [error for error in ethercat_dict.errors.errors] == expected_errors


@pytest.mark.no_connection
def test_read_xdf_register():
    dictionary_path = join_path(path_resources, "test_dict_ethercat.xdf")
    idx = 0x580F
    subidx = 0x00
    reg_id = "DRV_DIAG_ERROR_LAST_COM"
    subnode = 0

    ethercat_dict = EthercatDictionary(dictionary_path)

    assert ethercat_dict.registers(subnode)[reg_id].idx == idx
    assert ethercat_dict.registers(subnode)[reg_id].subidx == subidx


@pytest.mark.no_connection
@pytest.mark.parametrize(
    "register_uid, subnode, idx",
    [("DIST_CFG_REG0_MAP", 0, 0x5890), ("DRV_OP_CMD", 1, 0x2014), ("DRV_STATE_CONTROL", 2, 0x2810)],
)
def test_mcb_to_can_mapping(register_uid, subnode, idx):
    dictionary_path = join_path(path_resources, "test_dict_ethercat_axis.xdf")

    ethercat_dict = EthercatDictionary(dictionary_path)

    ethercat_register = ethercat_dict.registers(subnode)[register_uid]
    assert ethercat_register.idx == idx
