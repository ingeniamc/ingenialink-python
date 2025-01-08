from os.path import join as join_path

import pytest

from ingenialink import CanopenRegister
from ingenialink.bitfield import BitField
from ingenialink.dictionary import DictionaryV3, Interface, SubnodeType
from ingenialink.exceptions import ILDictionaryParseError

path_resources = "./tests/resources/canopen/"
dict_can_v3 = "test_dict_can_v3.0.xdf"
dict_can_v3_axis = "test_dict_can_v3.0_axis.xdf"
SINGLE_AXIS_BASE_SUBNODES = {0: SubnodeType.COMMUNICATION, 1: SubnodeType.MOTION}


@pytest.mark.no_connection()
def test_read_dictionary():
    dictionary_path = join_path(path_resources, dict_can_v3)
    expected_device_attr = {
        "path": dictionary_path,
        "version": "3.0",
        "firmware_version": "2.4.1",
        "product_code": 61939713,
        "part_number": "EVS-NET-C",
        "revision_number": 196617,
        "interface": Interface.CAN,
        "subnodes": SINGLE_AXIS_BASE_SUBNODES,
        "is_safe": False,
        "image": None,
    }

    canopen_dict = DictionaryV3(dictionary_path, Interface.CAN)

    for attr, value in expected_device_attr.items():
        assert getattr(canopen_dict, attr) == value


@pytest.mark.no_connection()
def test_read_dictionary_file_not_found():
    dictionary_path = "false.xdf"

    with pytest.raises(FileNotFoundError):
        DictionaryV3(dictionary_path, Interface.CAN)


@pytest.mark.no_connection()
def test_read_dictionary_registers():
    dictionary_path = join_path(path_resources, dict_can_v3)
    expected_regs_per_subnode = {
        0: [
            "DRV_DIAG_ERROR_LAST_COM",
            "DRV_AXIS_NUMBER",
            "CIA301_COMMS_RPDO1",
            "CIA301_COMMS_RPDO1_1",
            "CIA301_COMMS_RPDO1_2",
            "CIA301_COMMS_RPDO1_3",
            "CIA301_COMMS_RPDO1_MAP",
            "CIA301_COMMS_RPDO1_MAP_1",
        ],
        1: ["COMMU_ANGLE_SENSOR", "DRV_STATE_CONTROL"],
    }

    canopen_dict = DictionaryV3(dictionary_path, Interface.CAN)

    for subnode in expected_regs_per_subnode:
        assert expected_regs_per_subnode[subnode] == list(canopen_dict.registers(subnode))


@pytest.mark.no_connection()
def test_read_dictionary_registers_multiaxis():
    expected_num_registers_per_subnode = {0: 4, 1: 1, 2: 1}
    dictionary_path = join_path(path_resources, dict_can_v3_axis)

    canopen_dict = DictionaryV3(dictionary_path, Interface.CAN)
    assert canopen_dict.subnodes == {
        0: SubnodeType.COMMUNICATION,
        1: SubnodeType.MOTION,
        2: SubnodeType.MOTION,
    }
    for subnode in expected_num_registers_per_subnode:
        num_registers = len(canopen_dict.registers(subnode))
        assert num_registers == expected_num_registers_per_subnode[subnode]


@pytest.mark.no_connection()
def test_read_dictionary_categories():
    expected_categories = [
        "OTHERS",
        "IDENTIFICATION",
    ]
    dictionary_path = join_path(path_resources, dict_can_v3)

    canopen_dict = DictionaryV3(dictionary_path, Interface.CAN)

    assert canopen_dict.categories.category_ids == expected_categories


@pytest.mark.no_connection()
def test_read_dictionary_errors():
    expected_errors = [
        0x00003280,
        0x00002280,
    ]
    dictionary_path = join_path(path_resources, dict_can_v3)

    canopen_dict = DictionaryV3(dictionary_path, Interface.CAN)

    assert list(canopen_dict.errors) == expected_errors


@pytest.mark.no_connection()
def test_read_xdf_register():
    dictionary_path = join_path(path_resources, dict_can_v3)
    idx = 0x580F
    subidx = 0x00
    reg_id = "DRV_DIAG_ERROR_LAST_COM"
    subnode = 0

    canopen_dict = DictionaryV3(dictionary_path, Interface.CAN)
    target_register = canopen_dict.registers(subnode)[reg_id]

    assert isinstance(target_register, CanopenRegister)
    assert target_register.idx == idx
    assert target_register.subidx == subidx


@pytest.mark.no_connection()
def test_child_registers():
    dictionary_path = join_path(path_resources, dict_can_v3)
    canopen_dict = DictionaryV3(dictionary_path, Interface.CAN)
    reg_list = canopen_dict.child_registers("CIA301_COMMS_RPDO1_MAP", 0)
    reg_subindex = [0, 1]
    reg_uids = ["CIA301_COMMS_RPDO1_MAP", "CIA301_COMMS_RPDO1_MAP_1"]
    reg_index = [0x1600, 0x1600]
    for index, reg in enumerate(reg_list):
        assert isinstance(reg, CanopenRegister)
        assert reg.idx == reg_index[index]
        assert reg.identifier == reg_uids[index]
        assert reg.subidx == reg_subindex[index]


@pytest.mark.no_connection()
def test_child_registers_not_exist():
    dictionary_path = join_path(path_resources, dict_can_v3)
    canopen_dict = DictionaryV3(dictionary_path, Interface.CAN)
    with pytest.raises(KeyError):
        canopen_dict.child_registers("NOT_EXISTING_UID", 0)


@pytest.mark.no_connection()
def test_safety_pdo_not_implemented():
    dictionary_path = join_path(path_resources, dict_can_v3)
    canopen_dict = DictionaryV3(dictionary_path, Interface.CAN)
    with pytest.raises(NotImplementedError):
        canopen_dict.get_safety_rpdo("NOT_EXISTING_UID")
    with pytest.raises(NotImplementedError):
        canopen_dict.get_safety_tpdo("NOT_EXISTING_UID")


@pytest.mark.no_connection()
def test_wrong_dictionary():
    with pytest.raises(
        ILDictionaryParseError,
        match="Dictionary cannot be used for the chosen communication",
    ):
        DictionaryV3("./tests/resources/test_dict_ecat_eoe_v3.0.xdf", Interface.CAN)


@pytest.mark.no_connection()
@pytest.mark.parametrize("dictionary_path", [dict_can_v3, dict_can_v3_axis])
def test_register_default_values(dictionary_path):
    dictionary_path = join_path(path_resources, dictionary_path)
    expected_defaults_per_subnode = {
        0: {
            "DRV_DIAG_ERROR_LAST_COM": 0,
            "DRV_AXIS_NUMBER": 1,
            "CIA301_COMMS_RPDO1_MAP": 1,
            "CIA301_COMMS_RPDO1_MAP_1": 268451936,
            "CIA301_COMMS_RPDO1": 3,
            "CIA301_COMMS_RPDO1_1": 2,
            "CIA301_COMMS_RPDO1_2": 1,
            "CIA301_COMMS_RPDO1_3": 0,
        },
        1: {"COMMU_ANGLE_SENSOR": 4, "DRV_STATE_CONTROL": 0},
        2: {
            "COMMU_ANGLE_SENSOR": 4,
        },
    }
    canopen_dict = DictionaryV3(dictionary_path, Interface.CAN)
    for subnode, registers in canopen_dict._registers.items():
        for register in registers.values():
            assert register.default == expected_defaults_per_subnode[subnode][register.identifier]


@pytest.mark.no_connection()
@pytest.mark.parametrize("dictionary_path", [dict_can_v3, dict_can_v3_axis])
def test_register_description(dictionary_path):
    dictionary_path = join_path(path_resources, dictionary_path)
    expected_description_per_subnode = {
        0: {
            "DRV_DIAG_ERROR_LAST_COM": "Contains the last generated error",
            "DRV_AXIS_NUMBER": "",
            "CIA301_COMMS_RPDO1_MAP": "",
            "CIA301_COMMS_RPDO1_MAP_1": "",
            "CIA301_COMMS_RPDO1": "",
            "CIA301_COMMS_RPDO1_1": "COB-Id used",
            "CIA301_COMMS_RPDO1_2": "Transmission type",
            "CIA301_COMMS_RPDO1_3": "Inhibit time",
        },
        1: {
            "COMMU_ANGLE_SENSOR": "Indicates the sensor used for angle readings",
            "DRV_STATE_CONTROL": "Parameter to manage the drive state machine. "
            "It is compliant with DS402.",
        },
        2: {
            "COMMU_ANGLE_SENSOR": "Indicates the sensor used for angle readings",
        },
    }
    canopen_dict = DictionaryV3(dictionary_path, Interface.CAN)
    for subnode, registers in canopen_dict._registers.items():
        for register in registers.values():
            assert (
                register.description
                == expected_description_per_subnode[subnode][register.identifier]
            )


def test_register_bitfields():
    dictionary_path = join_path(path_resources, dict_can_v3)
    canopen_dict = DictionaryV3(dictionary_path, Interface.CAN)

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


@pytest.mark.no_connection()
def test_register_is_node_id_dependent():
    dictionary_path = join_path(path_resources, dict_can_v3)
    canopen_dict = DictionaryV3(dictionary_path, Interface.CAN)
    assert canopen_dict.registers(0)["CIA301_COMMS_RPDO1_1"].is_node_id_dependent
    assert not canopen_dict.registers(0)["CIA301_COMMS_RPDO1_2"].is_node_id_dependent
    assert not canopen_dict.registers(0)["CIA301_COMMS_RPDO1_3"].is_node_id_dependent
