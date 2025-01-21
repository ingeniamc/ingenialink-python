from os.path import join as join_path

import pytest

from ingenialink.bitfield import BitField
from ingenialink.dictionary import DictionaryV3, Interface, SubnodeType

path_resources = "./tests/resources/"
dict_eoe_v3 = "test_dict_ecat_eoe_v3.0.xdf"
SINGLE_AXIS_BASE_SUBNODES = {0: SubnodeType.COMMUNICATION, 1: SubnodeType.MOTION}


@pytest.mark.no_connection
def test_read_dictionary():
    dictionary_path = join_path(path_resources, dict_eoe_v3)
    expected_device_attr = {
        "path": dictionary_path,
        "version": "3.0",
        "firmware_version": "2.4.1",
        "product_code": 61939713,
        "part_number": "EVS-NET-E",
        "revision_number": 196617,
        "interface": Interface.EoE,
        "subnodes": SINGLE_AXIS_BASE_SUBNODES,
        "is_safe": False,
        "image": "image-text",
    }

    ethercat_dict = DictionaryV3(dictionary_path, Interface.EoE)

    for attr, value in expected_device_attr.items():
        assert getattr(ethercat_dict, attr) == value


@pytest.mark.no_connection
def test_read_dictionary_file_not_found():
    dictionary_path = "false.xdf"

    with pytest.raises(FileNotFoundError):
        DictionaryV3(dictionary_path, Interface.EoE)


@pytest.mark.no_connection
def test_read_dictionary_registers():
    dictionary_path = join_path(path_resources, dict_eoe_v3)
    expected_regs_per_subnode = {
        0: [
            "DRV_DIAG_ERROR_LAST_COM",
            "DRV_AXIS_NUMBER",
        ],
        1: ["COMMU_ANGLE_SENSOR", "DRV_STATE_CONTROL"],
    }

    ethercat_dict = DictionaryV3(dictionary_path, Interface.EoE)

    for subnode in expected_regs_per_subnode:
        assert expected_regs_per_subnode[subnode] == list(ethercat_dict.registers(subnode))


@pytest.mark.no_connection
def test_read_dictionary_categories():
    expected_categories = [
        "OTHERS",
        "IDENTIFICATION",
    ]
    dictionary_path = join_path(path_resources, dict_eoe_v3)

    ethercat_dict = DictionaryV3(dictionary_path, Interface.EoE)

    assert ethercat_dict.categories.category_ids == expected_categories


@pytest.mark.no_connection
def test_read_dictionary_errors():
    expected_errors = [
        0x00003280,
        0x00002280,
    ]
    dictionary_path = join_path(path_resources, dict_eoe_v3)

    ethercat_dict = DictionaryV3(dictionary_path, Interface.EoE)

    assert list(ethercat_dict.errors) == expected_errors


@pytest.mark.no_connection
def test_child_registers_not_exist():
    dictionary_path = join_path(path_resources, dict_eoe_v3)
    ethernet_dict = DictionaryV3(dictionary_path, Interface.EoE)
    with pytest.raises(KeyError):
        ethernet_dict.child_registers("NOT_EXISTING_UID", 0)


@pytest.mark.no_connection
def test_safety_pdo_not_implemented():
    dictionary_path = join_path(path_resources, dict_eoe_v3)
    ethernet_dict = DictionaryV3(dictionary_path, Interface.EoE)
    with pytest.raises(NotImplementedError):
        ethernet_dict.get_safety_rpdo("NOT_EXISTING_UID")
    with pytest.raises(NotImplementedError):
        ethernet_dict.get_safety_tpdo("NOT_EXISTING_UID")


@pytest.mark.no_connection
def test_register_default_values():
    dictionary_path = join_path(path_resources, dict_eoe_v3)
    expected_defaults_per_subnode = {
        0: {
            "DRV_DIAG_ERROR_LAST_COM": 0,
            "DRV_AXIS_NUMBER": 1,
            "CIA301_COMMS_RPDO1_MAP": 1,
            "CIA301_COMMS_RPDO1_MAP_1": 268451936,
        },
        1: {"COMMU_ANGLE_SENSOR": 4, "DRV_STATE_CONTROL": 0},
    }
    ethercat_dict = DictionaryV3(dictionary_path, Interface.EoE)
    for subnode, registers in ethercat_dict._registers.items():
        for register in registers.values():
            assert register.default == expected_defaults_per_subnode[subnode][register.identifier]


@pytest.mark.no_connection
def test_register_description():
    dictionary_path = join_path(path_resources, dict_eoe_v3)
    expected_description_per_subnode = {
        0: {
            "DRV_DIAG_ERROR_LAST_COM": "Contains the last generated error",
            "DRV_AXIS_NUMBER": "",
            "CIA301_COMMS_RPDO1_MAP": "",
            "CIA301_COMMS_RPDO1_MAP_1": "",
        },
        1: {
            "COMMU_ANGLE_SENSOR": "Indicates the sensor used for angle readings",
            "DRV_STATE_CONTROL": "Parameter to manage the drive state machine. "
            "It is compliant with DS402.",
        },
    }
    ethercat_dict = DictionaryV3(dictionary_path, Interface.EoE)
    for subnode, registers in ethercat_dict._registers.items():
        for register in registers.values():
            assert (
                register.description
                == expected_description_per_subnode[subnode][register.identifier]
            )


def test_register_bitfields():
    dictionary_path = join_path(path_resources, dict_eoe_v3)
    canopen_dict = DictionaryV3(dictionary_path, Interface.EoE)

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
