import contextlib
import time

from bitarray import bitarray

import tests.resources.ethercat

with contextlib.suppress(ImportError):
    import pysoem
import pytest

from ingenialink.dictionary import CanOpenObject, CanOpenObjectType, Interface
from ingenialink.enums.register import RegAccess, RegCyclicType, RegDtype
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.exceptions import ILEcatStateError, ILError
from ingenialink.pdo import RPDOMap, RPDOMapItem, TPDOMap, TPDOMapItem
from ingenialink.register import Register
from ingenialink.servo import DictionaryFactory
from ingenialink.utils._utils import convert_dtype_to_bytes, dtype_length_bits

TPDO_REGISTERS = ["CL_POS_FBK_VALUE", "CL_VEL_FBK_VALUE"]
RPDO_REGISTERS = ["CL_POS_SET_POINT_VALUE", "CL_VEL_SET_POINT_VALUE"]
SUBNODE = 1


@pytest.fixture()
def open_dictionary():
    dictionary = tests.resources.ethercat.TEST_DICT_ETHERCAT
    ethercat_dictionary = DictionaryFactory.create_dictionary(dictionary, Interface.ECAT)
    return ethercat_dictionary


@pytest.fixture()
def create_pdo_map(open_dictionary):
    ethercat_dictionary = open_dictionary
    rpdo_map = RPDOMap()
    tpdo_map = TPDOMap()

    for tpdo_register in TPDO_REGISTERS:
        register = ethercat_dictionary.registers(SUBNODE)[tpdo_register]
        tpdo_map.add_registers(register)
    for rpdo_register in RPDO_REGISTERS:
        register = ethercat_dictionary.registers(SUBNODE)[rpdo_register]
        rpdo_map.add_registers(register)

    return tpdo_map, rpdo_map


@pytest.mark.no_connection
def test_pdo_text_representation(create_pdo_map):
    tpdo_map, _rpdo_map = create_pdo_map

    assert tpdo_map.get_text_representation(item_space=20) == (
        "Item                 | Position bytes..bits | Size bytes..bits    \n"
        "CL_POS_FBK_VALUE     | 0..0                 | 4..0                \n"
        "CL_VEL_FBK_VALUE     | 4..0                 | 4..0                "
    )


@pytest.mark.no_connection
def test_rpdo_item(open_dictionary):
    ethercat_dictionary = open_dictionary
    register = ethercat_dictionary.registers(SUBNODE)[RPDO_REGISTERS[0]]
    rpdo_item = RPDOMapItem(register)

    assert rpdo_item.register == register
    assert rpdo_item.size_bits == dtype_length_bits[rpdo_item.register.dtype]

    with pytest.raises(ILError) as exc_info:
        rpdo_item.value
    assert str(exc_info.value) == "Raw data is empty."

    rpdo_item.value = 15
    assert rpdo_item.value == 15
    assert rpdo_item.raw_data_bytes == b"\x0f\x00\x00\x00"
    assert rpdo_item.raw_data_bits.to01() == "11110000000000000000000000000000"


@pytest.mark.no_connection
def test_rpdo_item_wrong_cyclic(open_dictionary):
    ethercat_dictionary = open_dictionary
    register = ethercat_dictionary.registers(SUBNODE)[TPDO_REGISTERS[0]]
    with pytest.raises(ILError) as exc_info:
        RPDOMapItem(register)
    assert (
        str(exc_info.value) == "Incorrect pdo access for mapping register CL_POS_FBK_VALUE. "
        "It should be RegCyclicType.RX, "
        "RegCyclicType.SAFETY_OUTPUT, "
        "RegCyclicType.SAFETY_INPUT_OUTPUT. "
        "obtained: RegCyclicType.TX"
    )


@pytest.mark.no_connection
def test_tpdo_item_wrong_cyclic(open_dictionary):
    ethercat_dictionary = open_dictionary
    register = ethercat_dictionary.registers(SUBNODE)[RPDO_REGISTERS[0]]
    with pytest.raises(ILError) as exc_info:
        TPDOMapItem(register)
    assert (
        str(exc_info.value) == "Incorrect pdo access for mapping register CL_POS_SET_POINT_VALUE. "
        "It should be RegCyclicType.TX, "
        "RegCyclicType.SAFETY_INPUT, "
        "RegCyclicType.SAFETY_INPUT_OUTPUT. "
        "obtained: RegCyclicType.RX"
    )


@pytest.mark.no_connection
def test_tpdo_item(open_dictionary):
    ethercat_dictionary = open_dictionary
    register = ethercat_dictionary.registers(SUBNODE)[TPDO_REGISTERS[0]]
    tpdo_item = TPDOMapItem(register)

    assert tpdo_item.register == register
    assert tpdo_item.size_bits == dtype_length_bits[tpdo_item.register.dtype]

    with pytest.raises(ILError) as exc_info:
        tpdo_item.value
    assert str(exc_info.value) == "Raw data is empty."

    with pytest.raises(AttributeError):
        tpdo_item.value = 15

    tpdo_item.raw_data_bytes = convert_dtype_to_bytes(15, tpdo_item.register.dtype)
    assert tpdo_item.value == 15


@pytest.mark.no_connection
@pytest.mark.parametrize(
    "uid, expected_value",
    [("CL_POS_FBK_VALUE", 0x20300020), ("CL_VEL_FBK_VALUE", 0x20310020)],
)
def test_pdo_item_register_mapping(open_dictionary, uid, expected_value):
    ethercat_dictionary = open_dictionary
    register = ethercat_dictionary.registers(1)[uid]
    tpdo_item = TPDOMapItem(register)

    assert expected_value == tpdo_item.register_mapping


@pytest.mark.no_connection
def test_pdo_create_item(open_dictionary):
    ethercat_dictionary = open_dictionary
    rpdo_map = RPDOMap()
    register = ethercat_dictionary.registers(SUBNODE)[RPDO_REGISTERS[0]]

    item = rpdo_map.create_item(register)
    assert item.register == register


@pytest.mark.no_connection
def test_pdo_add_item(open_dictionary):
    ethercat_dictionary = open_dictionary
    rpdo_map = RPDOMap()
    register = ethercat_dictionary.registers(SUBNODE)[RPDO_REGISTERS[0]]

    assert len(rpdo_map.items) == 0
    item = rpdo_map.create_item(register)
    rpdo_map.add_item(item)

    assert len(rpdo_map.items) == 1
    assert rpdo_map.items[0] == item


@pytest.mark.no_connection
def test_pdo_add_registers(open_dictionary):
    ethercat_dictionary = open_dictionary
    rpdo_map = RPDOMap()

    register1 = ethercat_dictionary.registers(SUBNODE)[RPDO_REGISTERS[0]]
    register2 = ethercat_dictionary.registers(SUBNODE)[RPDO_REGISTERS[1]]

    assert len(rpdo_map.items) == 0
    rpdo_map.add_registers(register1)

    assert len(rpdo_map.items) == 1
    assert rpdo_map.items[0].register == register1

    rpdo_map.add_registers([register1, register2])

    assert len(rpdo_map.items) == 3
    assert rpdo_map.items[0].register == register1
    assert rpdo_map.items[1].register == register1
    assert rpdo_map.items[2].register == register2


@pytest.mark.no_connection
def test_pdo_map(create_pdo_map):
    tpdo_map, rpdo_map = create_pdo_map

    assert len(rpdo_map.items) == len(RPDO_REGISTERS)
    assert len(tpdo_map.items) == len(TPDO_REGISTERS)

    assert all(isinstance(pdo_map_item, TPDOMapItem) for pdo_map_item in tpdo_map.items)
    assert all(isinstance(pdo_map_item, RPDOMapItem) for pdo_map_item in rpdo_map.items)

    assert all(isinstance(pdo_map_item.register, Register) for pdo_map_item in tpdo_map.items)
    assert all(isinstance(pdo_map_item.register, Register) for pdo_map_item in rpdo_map.items)

    assert all(
        pdo_map_item.size_bits == dtype_length_bits[pdo_map_item.register.dtype]
        for pdo_map_item in tpdo_map.items
    )
    assert all(
        pdo_map_item.size_bits == dtype_length_bits[pdo_map_item.register.dtype]
        for pdo_map_item in tpdo_map.items
    )

    assert tpdo_map.map_register_index is None
    assert rpdo_map.map_register_index is None


@pytest.mark.ethercat
def test_servo_add_maps(servo, create_pdo_map):
    tpdo_map, rpdo_map = create_pdo_map

    servo.reset_tpdo_mapping()
    servo.reset_rpdo_mapping()

    assert servo.read(EthercatServo.ETG_COMMS_TPDO_ASSIGN_TOTAL, subnode=0) == 0
    assert servo.read(EthercatServo.ETG_COMMS_RPDO_ASSIGN_TOTAL, subnode=0) == 0

    servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
    servo.map_pdos(1)

    assert servo.read(EthercatServo.ETG_COMMS_TPDO_ASSIGN_TOTAL, subnode=0) == 1
    assert len(servo._tpdo_maps) == 1
    assert tpdo_map.map_register_index == servo.dictionary.get_object("ETG_COMMS_TPDO_MAP1").idx
    assert tpdo_map.map_register_index_bytes == tpdo_map.map_register_index.to_bytes(2, "little")
    assert servo.read("ETG_COMMS_TPDO_MAP1_TOTAL", subnode=0) == len(TPDO_REGISTERS)
    value = servo._read_raw(
        servo.dictionary.registers(0)[EthercatServo.ETG_COMMS_TPDO_ASSIGN_TOTAL],
        complete_access=True,
    )
    assert int.to_bytes(0x1A00, 2, "little") == value[2:4]

    assert servo.read(EthercatServo.ETG_COMMS_RPDO_ASSIGN_TOTAL, subnode=0) == 1
    assert len(servo._rpdo_maps) == 1
    assert rpdo_map.map_register_index == servo.dictionary.get_object("ETG_COMMS_RPDO_MAP1").idx
    assert rpdo_map.map_register_index_bytes == rpdo_map.map_register_index.to_bytes(2, "little")
    assert servo.read("ETG_COMMS_RPDO_MAP1_TOTAL", subnode=0) == len(RPDO_REGISTERS)
    value = servo._read_raw(
        servo.dictionary.registers(0)[servo.ETG_COMMS_RPDO_ASSIGN_TOTAL], complete_access=True
    )
    assert int.to_bytes(0x1600, 2, "little") == value[2:4]


@pytest.mark.ethercat
def test_modifying_pdos_prevented_if_servo_is_not_in_preoperational_state(setup_manager):
    servo, net, _, _ = setup_manager
    operation_mode_uid = "DRV_OP_CMD"
    rpdo_registers = [operation_mode_uid]
    operation_mode_display_uid = "DRV_OP_VALUE"
    tpdo_registers = [operation_mode_display_uid]
    default_operation_mode = 1

    current_operation_mode = servo.read(operation_mode_uid)
    new_operation_mode = default_operation_mode
    if current_operation_mode == default_operation_mode:
        new_operation_mode += 1
    rpdo_map, tpdo_map = create_pdo_maps(servo, rpdo_registers, tpdo_registers)
    for item in rpdo_map.items:
        item.value = new_operation_mode
    servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])

    net._ecat_master.read_state()
    assert servo.slave.state_check(pysoem.PREOP_STATE) == pysoem.PREOP_STATE
    net.start_pdos()
    net._ecat_master.read_state()
    start_time = time.time()
    timeout = 1
    while time.time() < start_time + timeout:
        net.send_receive_processdata()
    assert servo.slave.state_check(pysoem.OP_STATE) == pysoem.OP_STATE

    locked_methods = {
        "reset_pdo_mapping": {"kwargs": {}},
        "reset_rpdo_mapping": {"kwargs": {}},
        "reset_tpdo_mapping": {"kwargs": {}},
        "map_pdos": {"kwargs": {"slave_index": 1}},
        "map_rpdos": {"kwargs": {}},
        "map_tpdos": {"kwargs": {}},
    }

    for method, method_args in locked_methods.items():
        with pytest.raises(ILEcatStateError):
            getattr(servo, method)(**method_args["kwargs"])


@pytest.mark.ethercat
def test_servo_reset_pdos(servo, create_pdo_map):
    tpdo_map, rpdo_map = create_pdo_map

    servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
    servo.map_pdos(1)

    assert servo.read(servo.ETG_COMMS_TPDO_ASSIGN_TOTAL, subnode=0) == 1
    assert servo.read(servo.ETG_COMMS_RPDO_ASSIGN_TOTAL, subnode=0) == 1
    assert len(servo._rpdo_maps) == 1
    assert len(servo._tpdo_maps) == 1

    servo.reset_tpdo_mapping()
    servo.reset_rpdo_mapping()

    assert servo.read(servo.ETG_COMMS_TPDO_ASSIGN_TOTAL, subnode=0) == 0
    assert servo.read(servo.ETG_COMMS_RPDO_ASSIGN_TOTAL, subnode=0) == 0
    assert len(servo._rpdo_maps) == 0
    assert len(servo._tpdo_maps) == 0


def create_pdo_maps(servo, rpdo_registers, tpdo_registers):
    rpdo_map = RPDOMap()
    tpdo_map = TPDOMap()
    for tpdo_register in tpdo_registers:
        register = servo.dictionary.registers(SUBNODE)[tpdo_register]
        tpdo_map.add_registers(register)
    for rpdo_register in rpdo_registers:
        register = servo.dictionary.registers(SUBNODE)[rpdo_register]
        rpdo_map.add_registers(register)
    return rpdo_map, tpdo_map


@pytest.mark.parametrize("from_uid", [True, False])
@pytest.mark.ethercat
def test_read_rpdo_map_from_slave(servo: EthercatServo, from_uid: bool):
    uid = "ETG_COMMS_RPDO_MAP1"
    if from_uid:
        pdo_map = servo.read_rpdo_map_from_slave(uid)
    else:
        obj = servo.dictionary.get_object(uid)
        pdo_map = servo.read_rpdo_map_from_slave(obj)

    assert pdo_map.map_register_index == 0x1600
    assert isinstance(pdo_map, RPDOMap)
    assert isinstance(pdo_map.map_object, CanOpenObject)
    assert pdo_map.map_object.idx == 0x1600
    assert pdo_map.map_object.object_type == CanOpenObjectType.RECORD
    assert pdo_map.map_object.uid == uid
    assert len(pdo_map.map_object.registers) == 16


@pytest.mark.parametrize("from_uid", [True, False])
@pytest.mark.ethercat
def test_read_tpdo_map_from_slave(servo: EthercatServo, from_uid: bool):
    uid = "ETG_COMMS_TPDO_MAP1"
    if from_uid:
        pdo_map = servo.read_tpdo_map_from_slave(uid)
    else:
        obj = servo.dictionary.get_object(uid)
        pdo_map = servo.read_tpdo_map_from_slave(obj)

    assert pdo_map.map_register_index == 0x1A00
    assert isinstance(pdo_map, TPDOMap)
    assert isinstance(pdo_map.map_object, CanOpenObject)
    assert pdo_map.map_object.idx == 0x1A00
    assert pdo_map.map_object.object_type == CanOpenObjectType.RECORD
    assert pdo_map.map_object.uid == uid
    assert len(pdo_map.map_object.registers) == 16


def test_map_register_items(servo: EthercatServo):
    pdo_map = servo.read_tpdo_map_from_slave("ETG_COMMS_TPDO_MAP1")

    item1 = pdo_map.create_item(servo.dictionary.get_register("CL_POS_FBK_VALUE"))
    item2 = pdo_map.create_item(servo.dictionary.get_register("DRV_STATE_STATUS"))
    item3 = pdo_map.create_item(servo.dictionary.get_register("CL_TOR_FBK_VALUE"))

    pdo_map.add_item(item1)
    pdo_map.add_item(item2)
    pdo_map.add_item(item3)

    assert {
        map_register.identifier: mapping_value
        for map_register, mapping_value in pdo_map.map_register_values().items()
    } == {
        "ETG_COMMS_TPDO_MAP1_TOTAL": 3,
        "ETG_COMMS_TPDO_MAP1_1": item1.register_mapping,
        "ETG_COMMS_TPDO_MAP1_2": item2.register_mapping,
        "ETG_COMMS_TPDO_MAP1_3": item3.register_mapping,
        "ETG_COMMS_TPDO_MAP1_4": None,
        "ETG_COMMS_TPDO_MAP1_5": None,
        "ETG_COMMS_TPDO_MAP1_6": None,
        "ETG_COMMS_TPDO_MAP1_7": None,
        "ETG_COMMS_TPDO_MAP1_8": None,
        "ETG_COMMS_TPDO_MAP1_9": None,
        "ETG_COMMS_TPDO_MAP1_10": None,
        "ETG_COMMS_TPDO_MAP1_11": None,
        "ETG_COMMS_TPDO_MAP1_12": None,
        "ETG_COMMS_TPDO_MAP1_13": None,
        "ETG_COMMS_TPDO_MAP1_14": None,
        "ETG_COMMS_TPDO_MAP1_15": None,
    }


def test_pdo_map_from_value(open_dictionary):
    tpdo_map = TPDOMap()

    # Full register mapped
    tpdo_map.add_registers(open_dictionary.get_register("CL_POS_FBK_VALUE"))
    # Padding item
    tpdo_map.add_item(TPDOMapItem(size_bits=8))
    # Partial register mapped
    tpdo_map.add_item(TPDOMapItem(open_dictionary.get_register("CL_VEL_FBK_VALUE"), size_bits=4))
    # Register that does not exist in the dictionary
    unknown_idx = 0x1234
    unknown_subidx = 0x10
    with pytest.raises(KeyError):
        open_dictionary.get_register_by_index_subindex(unknown_idx, unknown_subidx)
    not_existing_reg = EthercatRegister(
        identifier="CUSTOM_REGISTER",
        idx=unknown_idx,
        subidx=unknown_subidx,
        dtype=RegDtype.U32,
        access=RegAccess.RW,
        pdo_access=RegCyclicType.TX,
    )
    tpdo_map.add_registers(not_existing_reg)

    tpdo_value = tpdo_map.to_pdo_value()

    rebuild_tpdo_map = TPDOMap.from_pdo_value(
        tpdo_value, open_dictionary.get_object("ETG_COMMS_TPDO_MAP1"), open_dictionary
    )

    for original, rebuild in zip(tpdo_map.items, rebuild_tpdo_map.items):
        if original.register.idx == 0:
            # Padding item
            assert rebuild.register.idx == 0
            assert rebuild.register.subidx == 0
        elif original.register.idx == unknown_idx:
            # Register that does not exist in the dictionary
            assert rebuild.register.idx == unknown_idx
            assert rebuild.register.subidx == unknown_subidx
            assert rebuild.register.identifier == "UNKNOWN_REGISTER"
        else:
            assert original.register == rebuild.register

        assert original.size_bits == rebuild.size_bits


def start_stop_pdos(net):
    net._ecat_master.read_state()
    for servo in net.servos:
        assert servo.slave.state_check(pysoem.PREOP_STATE) == pysoem.PREOP_STATE
    net.start_pdos()
    net._ecat_master.read_state()
    start_time = time.time()
    timeout = 1
    while time.time() < start_time + timeout:
        net.send_receive_processdata()
    for servo in net.servos:
        assert servo.slave.state_check(pysoem.OP_STATE) == pysoem.OP_STATE
    net.stop_pdos()
    for servo in net.servos:
        assert servo.slave.state_check(pysoem.PREOP_STATE) == pysoem.PREOP_STATE


@pytest.mark.multislave
def test_start_stop_pdo(servo, net):
    operation_mode_uid = "DRV_OP_CMD"
    rpdo_registers = [operation_mode_uid]
    operation_mode_display_uid = "DRV_OP_VALUE"
    tpdo_registers = [operation_mode_display_uid]
    default_operation_mode = 1
    current_operation_mode = {}
    new_operation_mode = {}
    for index, s in enumerate(servo):
        current_operation_mode[index] = s.read(operation_mode_uid)
        new_operation_mode[index] = default_operation_mode
        if current_operation_mode[index] == default_operation_mode:
            new_operation_mode[index] += 1
        rpdo_map, tpdo_map = create_pdo_maps(s, rpdo_registers, tpdo_registers)
        for item in rpdo_map.items:
            item.value = new_operation_mode[index]
        s.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
    start_stop_pdos(net)
    for index, s in enumerate(servo):
        # Check that RPDOs are being received by the slave
        assert s._rpdo_maps[0x1600].items[0].value == s.read(operation_mode_uid)
        # Check that TPDOs are being sent by the slave
        assert s._tpdo_maps[0x1A00].items[0].value == s.read(tpdo_registers[0])
        # Restore the previous operation mode
        s.write(operation_mode_uid, current_operation_mode[index])
    # Check that PDOs can be re-started with the same configuration
    start_stop_pdos(net)
    # Re-configure the PDOs and re-start the PDO exchange
    for s in servo:
        s.remove_rpdo_map(rpdo_map_index=0x1600)
        s.remove_tpdo_map(tpdo_map_index=0x1A00)
        rpdo_map, tpdo_map = create_pdo_maps(s, RPDO_REGISTERS, TPDO_REGISTERS)
        for item in rpdo_map.items:
            item.value = 0
        s.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
    start_stop_pdos(net)


@pytest.mark.ethercat
def test_start_pdo_error_rpod_values_not_set(servo, net, create_pdo_map):
    tpdo_map, rpdo_map = create_pdo_map
    servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
    with pytest.raises(ILError):
        net.start_pdos()


@pytest.mark.ethercat
def test_set_pdo_map_to_slave(servo: EthercatServo, create_pdo_map):
    tpdo_map, rpdo_map = create_pdo_map
    servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
    # By default they are assigned to first pdo map
    assert len(servo._rpdo_maps) == 1
    assert servo._rpdo_maps[0x1600] == rpdo_map
    assert len(servo._tpdo_maps) == 1
    assert servo._tpdo_maps[0x1A00] == tpdo_map
    assert servo.slave.config_func is not None

    servo.map_pdos(1)
    # Check the current PDO mapping
    assert servo.read(servo.ETG_COMMS_TPDO_ASSIGN_TOTAL, subnode=0) == 1
    assert servo.read(servo.ETG_COMMS_RPDO_ASSIGN_TOTAL, subnode=0) == 1

    # Creating and setting new maps for the same index replaces the previous ones
    replace_rpdo_map = RPDOMap()
    replace_rpdo_map.map_register_index = rpdo_map.map_register_index
    replace_tpdo_map = TPDOMap()
    replace_tpdo_map.map_register_index = tpdo_map.map_register_index
    servo.set_pdo_map_to_slave([replace_rpdo_map], [replace_tpdo_map])
    assert len(servo._rpdo_maps) == 1
    assert servo._rpdo_maps[0x1600] == replace_rpdo_map
    assert len(servo._tpdo_maps) == 1
    assert servo._tpdo_maps[0x1A00] == replace_tpdo_map

    # Other pdo maps can be added as long as they use a different map
    other_rpdo_map = RPDOMap()
    other_rpdo_map.map_object = servo.dictionary.get_object("ETG_COMMS_RPDO_MAP2")
    other_tpdo_map = TPDOMap()
    other_tpdo_map.map_object = servo.dictionary.get_object("ETG_COMMS_TPDO_MAP2")
    servo.set_pdo_map_to_slave([other_rpdo_map], [other_tpdo_map])
    # Check that the new PDOMaps were added
    assert len(servo._rpdo_maps) == 2
    assert servo._rpdo_maps[0x1600] == replace_rpdo_map
    assert servo._rpdo_maps[0x1601] == other_rpdo_map
    assert len(servo._tpdo_maps) == 2
    assert servo._tpdo_maps[0x1A00] == replace_tpdo_map
    assert servo._tpdo_maps[0x1A01] == other_tpdo_map

    # Add same maps again
    servo.set_pdo_map_to_slave(
        [replace_rpdo_map, other_rpdo_map], [replace_tpdo_map, other_tpdo_map]
    )
    # Check that nothing changes
    assert len(servo._rpdo_maps) == 2
    assert servo._rpdo_maps[0x1600] == replace_rpdo_map
    assert servo._rpdo_maps[0x1601] == other_rpdo_map
    assert len(servo._tpdo_maps) == 2
    assert servo._tpdo_maps[0x1A00] == replace_tpdo_map
    assert servo._tpdo_maps[0x1A01] == other_tpdo_map


@pytest.mark.no_connection
def test_pdo_item_bool():
    register = EthercatRegister(0, 1, RegDtype.BOOL, RegAccess.RW, pdo_access=RegCyclicType.RX)
    rpdo_item = RPDOMapItem(register)

    assert rpdo_item.register == register
    assert rpdo_item.size_bits == 1

    with pytest.raises(ILError) as exc_info:
        rpdo_item.value
    assert str(exc_info.value) == "Raw data is empty."

    rpdo_item.value = True
    assert rpdo_item.raw_data_bits.to01() == "1"
    assert rpdo_item.raw_data_bytes == b"\x01"

    rpdo_item.value = False
    assert rpdo_item.raw_data_bits.to01() == "0"
    assert rpdo_item.raw_data_bytes == b"\x00"


@pytest.mark.no_connection
def test_pdo_item_custom_size(open_dictionary):
    ethercat_dictionary = open_dictionary
    register = ethercat_dictionary.registers(SUBNODE)[TPDO_REGISTERS[0]]

    tpdo_item = TPDOMapItem(register, size_bits=4)

    assert tpdo_item.size_bits == 4

    with pytest.raises(ILError) as exc_info:
        tpdo_item.value
    assert str(exc_info.value) == "Raw data is empty."

    tpdo_item.raw_data_bits = bitarray("1001")
    assert tpdo_item.raw_data_bytes == b"\x09"


@pytest.mark.no_connection
def test_pdo_item_custom_size_wrong_length(open_dictionary):
    ethercat_dictionary = open_dictionary
    register = ethercat_dictionary.registers(SUBNODE)[TPDO_REGISTERS[0]]

    tpdo_item = TPDOMapItem(register, size_bits=5)

    with pytest.raises(ILError) as exc_info:
        tpdo_item.raw_data_bits = bitarray("1001")

    assert str(exc_info.value) == "Wrong size. Expected 5, obtained 4"


@pytest.mark.no_connection
def test_rpdo_padding():
    size_bits = 3
    rpdo_item = RPDOMapItem(size_bits=size_bits)
    assert rpdo_item.size_bits == size_bits
    padding_register = rpdo_item.register
    assert isinstance(padding_register, EthercatRegister)
    assert padding_register.idx == 0x0000
    assert padding_register.subidx == 0x00
    assert padding_register.dtype == RegDtype.STR
    rpdo_item.raw_data_bytes = int.to_bytes(0, 1, "little")
    assert len(rpdo_item.raw_data_bits) == size_bits


@pytest.mark.no_connection
def test_tpdo_padding():
    size_bits = 4
    tpdo_item = TPDOMapItem(size_bits=size_bits)
    assert tpdo_item.size_bits == size_bits
    padding_register = tpdo_item.register
    assert isinstance(padding_register, EthercatRegister)
    assert padding_register.idx == 0x0000
    assert padding_register.subidx == 0x00
    assert padding_register.dtype == RegDtype.STR
    tpdo_item.raw_data_bytes = int.to_bytes(0, 1, "little")
    assert len(tpdo_item.raw_data_bits) == size_bits


@pytest.mark.no_connection
def test_pdo_padding_exceptions():
    # Size bits not defined
    with pytest.raises(ValueError):
        RPDOMapItem()
    padding_item = RPDOMapItem(size_bits=8)
    # Padding value cannot be set with the value attribute
    with pytest.raises(NotImplementedError) as exc_info:
        padding_item.value = int.to_bytes(0, 1, "little")
    assert str(exc_info.value) == "The register value must be set by the raw_data_bytes attribute."
    # Padding value cannot be read by the value attribute
    with pytest.raises(NotImplementedError) as exc_info:
        _ = padding_item.value
    assert str(exc_info.value) == "The register value must be read by the raw_data_bytes attribute."


@pytest.mark.no_connection
def test_map_pdo_with_bools(open_dictionary):
    ethercat_dictionary = open_dictionary
    register = ethercat_dictionary.registers(SUBNODE)[RPDO_REGISTERS[0]]
    item1 = RPDOMapItem(register)
    item2 = RPDOMapItem(register, size_bits=4)
    register = EthercatRegister(0, 1, RegDtype.BOOL, RegAccess.RW, pdo_access=RegCyclicType.RX)
    item3 = RPDOMapItem(register)
    item4 = RPDOMapItem(register)

    rpdo_map = RPDOMap()
    for item in [item1, item2, item3, item4]:
        rpdo_map.add_item(item)

    item1.value = 411601032
    item2.raw_data_bits = bitarray("1011")
    item3.value = False
    item4.value = True

    assert rpdo_map.data_length_bits == 32 + 4 + 1 + 1
    assert rpdo_map.data_length_bytes == 5
    assert item1.raw_data_bits.to01() == "00010001000100010001000100011000"
    assert item2.raw_data_bits.to01() == "1011"
    assert item3.raw_data_bits.to01() == "0"
    assert item4.raw_data_bits.to01() == "1"
    assert rpdo_map.get_item_bits().to01() == "00010001000100010001000100011000101101"
    assert rpdo_map.get_item_bytes() == b"\x88\x88\x88\x18-"


@pytest.mark.ethercat
def test_remove_rpdo_map(servo: EthercatServo, create_pdo_map):
    _, rpdo_map = create_pdo_map
    servo.set_pdo_map_to_slave([rpdo_map], [])
    assert len(servo._rpdo_maps) > 0
    servo.remove_rpdo_map(rpdo_map)
    assert len(servo._rpdo_maps) == 0
    servo._rpdo_maps[0x1600] = rpdo_map
    servo.remove_rpdo_map(rpdo_map_index=0x1600)
    assert len(servo._rpdo_maps) == 0


@pytest.mark.ethercat
def test_remove_rpdo_map_exceptions(servo: EthercatServo, create_pdo_map):
    tpdo_map, rpdo_map = create_pdo_map
    servo.set_pdo_map_to_slave([rpdo_map], [])
    with pytest.raises(ValueError):
        servo.remove_rpdo_map()
    with pytest.raises(ValueError):
        servo.remove_rpdo_map(tpdo_map)
    with pytest.raises(KeyError):
        servo.remove_rpdo_map(rpdo_map_index=0x1602)


@pytest.mark.ethercat
def test_remove_tpdo_map(servo, create_pdo_map):
    tpdo_map, _ = create_pdo_map
    servo.set_pdo_map_to_slave([], [tpdo_map])
    assert len(servo._tpdo_maps) > 0
    servo.remove_tpdo_map(tpdo_map)
    assert len(servo._tpdo_maps) == 0
    servo._tpdo_maps[0x1A00] = tpdo_map
    servo.remove_tpdo_map(tpdo_map_index=0x1A00)
    assert len(servo._tpdo_maps) == 0


@pytest.mark.ethercat
def test_remove_tpdo_map_exceptions(servo: EthercatServo, create_pdo_map):
    _, rpdo_map = create_pdo_map
    servo.set_pdo_map_to_slave([rpdo_map], [])
    with pytest.raises(ValueError):
        servo.remove_rpdo_map()
    with pytest.raises(ValueError):
        servo.remove_tpdo_map(rpdo_map)
    with pytest.raises(KeyError):
        servo.remove_tpdo_map(tpdo_map_index=0x1A01)


@pytest.mark.no_connection
def test_rpdo_map_set_items_bytes(create_pdo_map):
    _, rpdo_map = create_pdo_map
    data_bytes = b""
    for idx, item in enumerate(rpdo_map.items):
        data_bytes += convert_dtype_to_bytes(idx, item.register.dtype)
    rpdo_map.set_item_bytes(data_bytes)
    for idx, item in enumerate(rpdo_map.items):
        assert item.value == idx


@pytest.mark.no_connection
def test_tpdo_map_set_items_bytes(create_pdo_map):
    tpdo_map, _ = create_pdo_map
    data_bytes = b""
    for idx, item in enumerate(tpdo_map.items):
        data_bytes += convert_dtype_to_bytes(idx, item.register.dtype)
    tpdo_map.set_item_bytes(data_bytes)
    for idx, item in enumerate(tpdo_map.items):
        assert item.value == idx
