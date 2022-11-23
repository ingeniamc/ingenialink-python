import pytest
from os.path import join as join_path

from ingenialink.canopen.dictionary import CanopenDictionary


path_resources = "./tests/resources/canopen/"


@pytest.mark.no_connection
def test_read_dictionary():
    dictionary_path = join_path(path_resources, "test_dict_can.xdf")
    expected_device_attr = {
        "path" : dictionary_path,
        "version" : "2",
        "firmware_version" : "2.0.1",
        "product_code" : 57745409,
        "part_number" : "CAP-NET-C",
        "revision_number" : 196635,
        "interface" : "CAN",
        "subnodes" : 2
    }

    canopen_dict = CanopenDictionary(dictionary_path)
    
    for attr, value in expected_device_attr.items():
        assert getattr(canopen_dict, attr) == value


@pytest.mark.no_connection
def test_read_dictionary_file_not_found():
    dictionary_path = "false.xdf"
    
    with pytest.raises(FileNotFoundError):
        CanopenDictionary(dictionary_path)
    

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
        1 : [
            "COMMU_ANGLE_SENSOR"
        ]
    }

    canopen_dict = CanopenDictionary(dictionary_path)

    for subnode in expected_regs_per_subnode.keys():
        num_registers = len(canopen_dict.registers(subnode))
        assert num_registers == len(expected_regs_per_subnode[subnode])
        for register in canopen_dict.registers(subnode):
            assert register in expected_regs_per_subnode[subnode]


@pytest.mark.no_connection
def test_read_dictionary_registers_multiaxis():
    expected_num_registers_per_subnode = {0: 6, 1: 5, 2: 5}
    dictionary_path = join_path(path_resources, "test_dict_can_axis.xdf")

    canopen_dict = CanopenDictionary(dictionary_path)

    for subnode in expected_num_registers_per_subnode.keys():
        num_registers = len(canopen_dict.registers(subnode))
        assert num_registers == expected_num_registers_per_subnode[subnode]


@pytest.mark.no_connection
def test_read_dictionary_categories():
    expected_categories = [
        "IDENTIFICATION",
        "COMMUNICATIONS",
        "COMMUTATION",
        "REPORTING",
        "MONITORING"
    ]
    dictionary_path = join_path(path_resources, "test_dict_can.xdf")

    canopen_dict = CanopenDictionary(dictionary_path)

    assert len(canopen_dict.categories.category_ids) == len(expected_categories)
    for cat in expected_categories:
        assert cat in canopen_dict.categories.category_ids


@pytest.mark.no_connection
def test_read_dictionary_errors():
    expected_errors = [
        0x00003280,
        0x00007380,
        0x00007385,
        0x06010000,
    ]
    dictionary_path = join_path(path_resources, "test_dict_can.xdf")

    canopen_dict = CanopenDictionary(dictionary_path)

    assert len(canopen_dict.errors.errors) == len(expected_errors)
    for error in expected_errors:
        assert error in canopen_dict.errors.errors


@pytest.mark.no_connection
def test_read_xdf_register():
    dictionary_path = join_path(path_resources, "test_dict_can.xdf")
    idx = 0x580F
    subidx = 0x00
    reg_id = "DRV_DIAG_ERROR_LAST_COM"
    subnode = 0

    canopen_dict = CanopenDictionary(dictionary_path)
    
    assert canopen_dict.registers(subnode)[reg_id].idx == idx
    assert canopen_dict.registers(subnode)[reg_id].subidx == subidx
