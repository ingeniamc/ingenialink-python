from os.path import join as join_path

import pytest

from ingenialink import CanopenRegister
from ingenialink.bitfield import BitField
from ingenialink.dictionary import (
    DictionarySafetyModule,
    DictionarySafetyPDO,
    DictionaryV3,
    Interface,
    SubnodeType,
)
from ingenialink.exceptions import ILDictionaryParseError

path_resources = "./tests/resources/"
dict_ecat_v3 = "test_dict_ecat_eoe_v3.0.xdf"
dict_ecat_v3_safe = "test_dict_ecat_eoe_safe_v3.0.xdf"
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
            "TEST_RXTX_REGISTER",
            "DRV_AXIS_NUMBER",
            "CIA301_COMMS_RPDO1_MAP",
            "CIA301_COMMS_RPDO1_MAP_1",
        ],
        1: ["COMMU_ANGLE_SENSOR"],
    }

    ethercat_dict = DictionaryV3(dictionary_path, Interface.ECAT)

    for subnode in expected_regs_per_subnode:
        assert expected_regs_per_subnode[subnode] == list(ethercat_dict.registers(subnode))


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

    assert list(ethercat_dict.errors) == expected_errors


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
def test_object_registers():
    dictionary_path = join_path(path_resources, dict_ecat_v3)
    ethercat_dict = DictionaryV3(dictionary_path, Interface.ECAT)
    canopen_object = ethercat_dict.get_object("CIA301_COMMS_RPDO1_MAP", 0)
    reg_subindex = [0, 1]
    reg_uids = ["CIA301_COMMS_RPDO1_MAP", "CIA301_COMMS_RPDO1_MAP_1"]
    reg_index = [0x1600, 0x1600]
    for index, reg in enumerate(canopen_object):
        assert isinstance(reg, CanopenRegister)
        assert reg.idx == reg_index[index]
        assert reg.identifier == reg_uids[index]
        assert reg.subidx == reg_subindex[index]


@pytest.mark.no_connection
def test_object_not_exist():
    dictionary_path = join_path(path_resources, dict_ecat_v3)
    ethercat_dict = DictionaryV3(dictionary_path, Interface.ECAT)
    with pytest.raises(KeyError):
        ethercat_dict.get_object("NOT_EXISTING_UID", 0)


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
def test_safety_modules():
    dictionary_path = join_path(path_resources, dict_ecat_v3_safe)
    ethercat_dict = DictionaryV3(dictionary_path, Interface.ECAT)

    # Expected data
    module_ident_to_application_parameters = {
        "0x3800000": {
            "uses_sra": False,
            "application_parameters": ["FSOE_SAFE_INPUTS_MAP", "FSOE_SS1_TIME_TO_STO_1"],
        },
        "0x3800001": {
            "uses_sra": True,
            "application_parameters": ["FSOE_SAFE_INPUTS_MAP", "FSOE_SS1_TIME_TO_STO_1"],
        },
    }

    for module_ident, module_data in module_ident_to_application_parameters.items():
        expected_app_params = module_data["application_parameters"]
        safety_module = ethercat_dict.get_safety_module(module_ident=module_ident)
        assert isinstance(safety_module, DictionarySafetyModule)
        assert hex(safety_module.module_ident) == module_ident
        assert safety_module.uses_sra == module_data["uses_sra"]
        assert len(safety_module.application_parameters) == len(expected_app_params)
        for param in safety_module.application_parameters:
            assert param.uid in expected_app_params


@pytest.mark.no_connection
def test_safety_module_not_exist():
    dictionary_path = join_path(path_resources, dict_ecat_v3_safe)
    ethercat_dict = DictionaryV3(dictionary_path, Interface.ECAT)
    with pytest.raises(KeyError):
        ethercat_dict.get_safety_module("0x3800007")


@pytest.mark.no_connection
def test_wrong_dictionary():
    with pytest.raises(
        ILDictionaryParseError, match="Dictionary cannot be used for the chosen communication"
    ):
        DictionaryV3("./tests/resources/canopen/test_dict_can_v3.0.xdf", Interface.ECAT)


@pytest.mark.no_connection
def test_register_default_values():
    dictionary_path = join_path(path_resources, dict_ecat_v3)
    expected_defaults_per_subnode = {
        0: {
            "DRV_DIAG_ERROR_LAST_COM": 0,
            "DRV_AXIS_NUMBER": 1,
            "TEST_RXTX_REGISTER": 0,
            "CIA301_COMMS_RPDO1_MAP": 1,
            "CIA301_COMMS_RPDO1_MAP_1": 268451936,
        },
        1: {
            "COMMU_ANGLE_SENSOR": 4,
        },
    }
    ethercat_dict = DictionaryV3(dictionary_path, Interface.ECAT)
    for subnode, registers in ethercat_dict._registers.items():
        for register in registers.values():
            assert register.default == expected_defaults_per_subnode[subnode][register.identifier]


@pytest.mark.no_connection
def test_register_description():
    dictionary_path = join_path(path_resources, dict_ecat_v3)
    expected_description_per_subnode = {
        0: {
            "DRV_DIAG_ERROR_LAST_COM": "Contains the last generated error",
            "DRV_AXIS_NUMBER": "",
            "TEST_RXTX_REGISTER": "Test RXTX register",
            "CIA301_COMMS_RPDO1_MAP": "",
            "CIA301_COMMS_RPDO1_MAP_1": "",
        },
        1: {
            "COMMU_ANGLE_SENSOR": "Indicates the sensor used for angle readings",
        },
    }
    ethercat_dict = DictionaryV3(dictionary_path, Interface.ECAT)
    for subnode, registers in ethercat_dict._registers.items():
        for register in registers.values():
            assert (
                register.description
                == expected_description_per_subnode[subnode][register.identifier]
            )


@pytest.mark.no_connection
def test_register_bitfields():
    dictionary_path = join_path(path_resources, dict_ecat_v3)
    canopen_dict = DictionaryV3(dictionary_path, Interface.ECAT)

    for registers in canopen_dict._registers.values():
        for register in registers.values():
            if register.identifier == "DRV_STATE_CONTROL":
                assert register.bitfields == {
                    "SWITCH_ON": BitField.bit(0),
                    "VOLTAGE_ENABLE": BitField.bit(1),
                    "QUICK_STOP": BitField.bit(2),
                    "ENABLE_OPERATION": BitField.bit(3),
                    "RUN_SET_POINT_MANAGER": BitField.bit(4),
                    "FAULT_RESET": BitField.bit(7),
                    "OPERATION_MODE_SPECIFIC": BitField(8, 15),
                }
            else:
                assert register.bitfields is None
