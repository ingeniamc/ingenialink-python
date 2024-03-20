import pytest
from os.path import join as join_path

from ingenialink.exceptions import ILDictionaryParseError
from ingenialink import CanopenRegister
from ingenialink.dictionary import Interface, SubnodeType, DictionaryV3, DictionarySafetyPDO

path_resources = "./tests/resources/"
dict_ecat_v3 = "test_dict_ecat_eoe_v3.0.xdf"
SINGLE_AXIS_SAFETY_SUBNODES = {
    0: SubnodeType.COMMUNICATION,
    1: SubnodeType.MOTION,
    4: SubnodeType.SAFETY,
}


@pytest.mark.no_connection
def test_read_dictionary():
    dictionary_path = join_path(path_resources, dict_ecat_v3)
    expected_device_attr = {
        "path": dictionary_path,
        "version": "3.0",
        "firmware_version": "2.4.1",
        "product_code": 61939713,
        "part_number": "EVS-NET-E",
        "revision_number": 196617,
        "interface": Interface.ECAT,
        "subnodes": SINGLE_AXIS_SAFETY_SUBNODES,
        "is_safe": True,
        "image": "image-text",
    }

    ethercat_dict = DictionaryV3(dictionary_path, Interface.ECAT)

    for attr, value in expected_device_attr.items():
        assert getattr(ethercat_dict, attr) == value


@pytest.mark.no_connection
def test_read_dictionary_file_not_found():
    dictionary_path = "false.xdf"

    with pytest.raises(FileNotFoundError):
        DictionaryV3(dictionary_path, Interface.ECAT)


@pytest.mark.no_connection
def test_read_dictionary_registers():
    dictionary_path = join_path(path_resources, dict_ecat_v3)
    expected_regs_per_subnode = {
        0: [
            "DRV_DIAG_ERROR_LAST_COM",
            "DRV_AXIS_NUMBER",
            "CIA301_COMMS_RPDO1_MAP",
            "CIA301_COMMS_RPDO1_MAP_1",
        ],
        1: ["COMMU_ANGLE_SENSOR"],
    }

    ethercat_dict = DictionaryV3(dictionary_path, Interface.ECAT)

    for subnode in expected_regs_per_subnode.keys():
        assert expected_regs_per_subnode[subnode] == [
            reg for reg in ethercat_dict.registers(subnode)
        ]


@pytest.mark.no_connection
def test_read_dictionary_categories():
    expected_categories = [
        "OTHERS",
        "IDENTIFICATION",
    ]
    dictionary_path = join_path(path_resources, dict_ecat_v3)

    ethercat_dict = DictionaryV3(dictionary_path, Interface.ECAT)

    assert ethercat_dict.categories.category_ids == expected_categories


@pytest.mark.no_connection
def test_read_dictionary_errors():
    expected_errors = [
        0x00003280,
        0x00002280,
    ]
    dictionary_path = join_path(path_resources, dict_ecat_v3)

    ethercat_dict = DictionaryV3(dictionary_path, Interface.ECAT)

    assert [error for error in ethercat_dict.errors.errors] == expected_errors


@pytest.mark.no_connection
def test_read_xdf_register():
    dictionary_path = join_path(path_resources, dict_ecat_v3)
    idx = 0x580F
    subidx = 0x00
    reg_id = "DRV_DIAG_ERROR_LAST_COM"
    subnode = 0

    ethercat_dict = DictionaryV3(dictionary_path, Interface.ECAT)
    target_register = ethercat_dict.registers(subnode)[reg_id]

    assert isinstance(target_register, CanopenRegister)
    assert target_register.idx == idx
    assert target_register.subidx == subidx


@pytest.mark.no_connection
def test_child_registers():
    dictionary_path = join_path(path_resources, dict_ecat_v3)
    ethercat_dict = DictionaryV3(dictionary_path, Interface.ECAT)
    reg_list = ethercat_dict.child_registers("CIA301_COMMS_RPDO1_MAP", 0)
    reg_subindex = [0, 1]
    reg_uids = ["CIA301_COMMS_RPDO1_MAP", "CIA301_COMMS_RPDO1_MAP_1"]
    reg_index = [0x1600, 0x1600]
    for index, reg in enumerate(reg_list):
        assert isinstance(reg, CanopenRegister)
        assert reg.idx == reg_index[index]
        assert reg.identifier == reg_uids[index]
        assert reg.subidx == reg_subindex[index]


@pytest.mark.no_connection
def test_child_registers_not_exist():
    dictionary_path = join_path(path_resources, dict_ecat_v3)
    ethercat_dict = DictionaryV3(dictionary_path, Interface.ECAT)
    with pytest.raises(KeyError):
        ethercat_dict.child_registers("NOT_EXISTING_UID", 0)


@pytest.mark.no_connection
def test_safety_rpdo():
    dictionary_path = join_path(path_resources, dict_ecat_v3)
    ethercat_dict = DictionaryV3(dictionary_path, Interface.ECAT)
    safety_rpdo = ethercat_dict.get_safety_rpdo("READ_ONLY_RPDO_1")
    assert isinstance(safety_rpdo, DictionarySafetyPDO)
    assert safety_rpdo.index == 0x1700
    sizes = [32, 16, 16, 16]
    regs = [
        ("DRV_DIAG_ERROR_LAST_COM", 0),
        ("DRV_AXIS_NUMBER", 0),
        None,
        ("CIA301_COMMS_RPDO1_MAP", 0),
    ]
    for index, pdo_entry in enumerate(safety_rpdo.entries):
        assert pdo_entry.size == sizes[index]
        entry_reg = None
        if regs[index] is not None:
            entry_reg = ethercat_dict.registers(regs[index][1])[regs[index][0]]
        assert pdo_entry.register == entry_reg


@pytest.mark.no_connection
def test_safety_rpdo_not_exist():
    dictionary_path = join_path(path_resources, dict_ecat_v3)
    ethercat_dict = DictionaryV3(dictionary_path, Interface.ECAT)
    with pytest.raises(KeyError):
        ethercat_dict.get_safety_rpdo("READ_ONLY_TPDO_1")


@pytest.mark.no_connection
def test_safety_tpdo():
    dictionary_path = join_path(path_resources, dict_ecat_v3)
    ethercat_dict = DictionaryV3(dictionary_path, Interface.ECAT)
    safety_rpdo = ethercat_dict.get_safety_tpdo("READ_ONLY_TPDO_1")
    assert isinstance(safety_rpdo, DictionarySafetyPDO)
    assert safety_rpdo.index == 0x1B00
    sizes = [16, 16, 16, 32]
    regs = [
        ("CIA301_COMMS_RPDO1_MAP_1", 0),
        ("DRV_AXIS_NUMBER", 0),
        None,
        ("DRV_DIAG_ERROR_LAST_COM", 0),
    ]
    for index, pdo_entry in enumerate(safety_rpdo.entries):
        assert pdo_entry.size == sizes[index]
        entry_reg = None
        if regs[index] is not None:
            entry_reg = ethercat_dict.registers(regs[index][1])[regs[index][0]]
        assert pdo_entry.register == entry_reg


@pytest.mark.no_connection
def test_safety_tpdo_not_exist():
    dictionary_path = join_path(path_resources, dict_ecat_v3)
    ethercat_dict = DictionaryV3(dictionary_path, Interface.ECAT)
    with pytest.raises(KeyError):
        ethercat_dict.get_safety_tpdo("READ_ONLY_RPDO_1")


@pytest.mark.no_connection
def test_wrong_dictionary():
    with pytest.raises(
        ILDictionaryParseError, match="Dictionary can not be used for the chose communication"
    ):
        DictionaryV3("./tests/resources/canopen/test_dict_can_v3.0.xdf", Interface.ECAT)
