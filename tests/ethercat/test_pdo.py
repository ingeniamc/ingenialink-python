import contextlib
import json
import time

from bitarray import bitarray

with contextlib.suppress(ImportError):
    import pysoem
import pytest

from ingenialink import EthercatNetwork
from ingenialink.dictionary import Interface
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
    dictionary = "./tests/resources/ethercat/test_dict_ethercat.xdf"
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
        str(exc_info.value)
        == "Incorrect cyclic. It should be RegCyclicType.RX or RegCyclicType.TXRX, obtained:"
        " RegCyclicType.TX"
    )


@pytest.mark.no_connection
def test_tpdo_item_wrong_cyclic(open_dictionary):
    ethercat_dictionary = open_dictionary
    register = ethercat_dictionary.registers(SUBNODE)[RPDO_REGISTERS[0]]
    with pytest.raises(ILError) as exc_info:
        TPDOMapItem(register)
    assert (
        str(exc_info.value)
        == "Incorrect cyclic. It should be RegCyclicType.TX or RegCyclicType.TXRX, obtained:"
        " RegCyclicType.RX"
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
    assert expected_value.to_bytes(4, "little") == tpdo_item.register_mapping


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
def test_servo_add_maps(connect_to_slave, create_pdo_map):
    tpdo_map, rpdo_map = create_pdo_map
    servo, _ = connect_to_slave

    servo.reset_tpdo_mapping()
    servo.reset_rpdo_mapping()

    assert servo.read(EthercatServo.TPDO_ASSIGN_REGISTER_SUB_IDX_0, subnode=0) == 0
    assert servo.read(EthercatServo.RPDO_ASSIGN_REGISTER_SUB_IDX_0, subnode=0) == 0

    servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
    servo.map_pdos(1)

    assert servo.read(EthercatServo.TPDO_ASSIGN_REGISTER_SUB_IDX_0, subnode=0) == 1
    assert len(servo._tpdo_maps) == 1
    assert (
        tpdo_map.map_register_index
        == servo.dictionary.registers(0)[servo.TPDO_MAP_REGISTER_SUB_IDX_0[0]].idx
    )
    assert tpdo_map.map_register_index_bytes == tpdo_map.map_register_index.to_bytes(2, "little")
    assert servo.read(EthercatServo.TPDO_MAP_REGISTER_SUB_IDX_0[0], subnode=0) == len(
        TPDO_REGISTERS
    )
    value = servo._read_raw(
        servo.dictionary.registers(0)[servo.TPDO_ASSIGN_REGISTER_SUB_IDX_0], complete_access=True
    )
    assert int.to_bytes(0x1A00, 2, "little") == value[2:4]

    assert servo.read(EthercatServo.RPDO_ASSIGN_REGISTER_SUB_IDX_0, subnode=0) == 1
    assert len(servo._rpdo_maps) == 1
    assert (
        rpdo_map.map_register_index
        == servo.dictionary.registers(0)[servo.RPDO_MAP_REGISTER_SUB_IDX_0[0]].idx
    )
    assert rpdo_map.map_register_index_bytes == rpdo_map.map_register_index.to_bytes(2, "little")
    assert servo.read(EthercatServo.RPDO_MAP_REGISTER_SUB_IDX_0[0], subnode=0) == len(
        RPDO_REGISTERS
    )
    value = servo._read_raw(
        servo.dictionary.registers(0)[servo.RPDO_ASSIGN_REGISTER_SUB_IDX_0], complete_access=True
    )
    assert int.to_bytes(0x1600, 2, "little") == value[2:4]


@pytest.mark.ethercat
def test_modifying_pdos_prevented_if_servo_is_not_in_preoperational_state(connect_to_slave):
    servo, net = connect_to_slave

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
def test_servo_reset_pdos(connect_to_slave, create_pdo_map):
    tpdo_map, rpdo_map = create_pdo_map
    servo, _ = connect_to_slave

    servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
    servo.map_pdos(1)

    assert servo.read(servo.TPDO_ASSIGN_REGISTER_SUB_IDX_0, subnode=0) == 1
    assert servo.read(servo.RPDO_ASSIGN_REGISTER_SUB_IDX_0, subnode=0) == 1
    assert len(servo._rpdo_maps) == 1
    assert len(servo._tpdo_maps) == 1

    servo.reset_tpdo_mapping()
    servo.reset_rpdo_mapping()

    assert servo.read(servo.TPDO_ASSIGN_REGISTER_SUB_IDX_0, subnode=0) == 0
    assert servo.read(servo.RPDO_ASSIGN_REGISTER_SUB_IDX_0, subnode=0) == 0
    assert len(servo._rpdo_maps) == 0
    assert len(servo._tpdo_maps) == 0


@pytest.fixture
def connect_to_all_slave(pytestconfig):
    protocol = pytestconfig.getoption("--protocol")
    if protocol != "multislave":
        raise AssertionError("Wrong protocol")
    config = "tests/config.json"
    with open(config, encoding="utf-8") as fp:
        contents = json.load(fp)
    protocol_contents = contents["ethercat"]
    net = EthercatNetwork(protocol_contents[0]["ifname"])
    servos = [
        net.connect_to_slave(slave_content["slave"], slave_content["dictionary"])
        for slave_content in protocol_contents
    ]
    yield servos, net
    for servo in servos:
        net.disconnect_from_slave(servo)


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
def test_start_stop_pdo(connect_to_all_slave):
    servos, net = connect_to_all_slave
    operation_mode_uid = "DRV_OP_CMD"
    rpdo_registers = [operation_mode_uid]
    operation_mode_display_uid = "DRV_OP_VALUE"
    tpdo_registers = [operation_mode_display_uid]
    default_operation_mode = 1
    current_operation_mode = {}
    new_operation_mode = {}
    for index, servo in enumerate(servos):
        current_operation_mode[index] = servo.read(operation_mode_uid)
        new_operation_mode[index] = default_operation_mode
        if current_operation_mode[index] == default_operation_mode:
            new_operation_mode[index] += 1
        rpdo_map, tpdo_map = create_pdo_maps(servo, rpdo_registers, tpdo_registers)
        for item in rpdo_map.items:
            item.value = new_operation_mode[index]
        servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
    start_stop_pdos(net)
    for index, servo in enumerate(servos):
        # Check that RPDOs are being received by the slave
        assert servo._rpdo_maps[0].items[0].value == servo.read(operation_mode_uid)
        # Check that TPDOs are being sent by the slave
        assert servo._tpdo_maps[0].items[0].value == servo.read(tpdo_registers[0])
        # Restore the previous operation mode
        servo.write(operation_mode_uid, current_operation_mode[index])
    # Check that PDOs can be re-started with the same configuration
    start_stop_pdos(net)
    # Re-configure the PDOs and re-start the PDO exchange
    for servo in servos:
        servo.remove_rpdo_map(rpdo_map_index=0)
        servo.remove_tpdo_map(tpdo_map_index=0)
        rpdo_map, tpdo_map = create_pdo_maps(servo, RPDO_REGISTERS, TPDO_REGISTERS)
        for item in rpdo_map.items:
            item.value = 0
        servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
    start_stop_pdos(net)


@pytest.mark.ethercat
def test_start_pdo_error_rpod_values_not_set(connect_to_slave, create_pdo_map):
    tpdo_map, rpdo_map = create_pdo_map
    servo, net = connect_to_slave
    servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
    with pytest.raises(ILError):
        net.start_pdos()


@pytest.mark.ethercat
def test_set_pdo_map_to_slave(connect_to_slave, create_pdo_map):
    tpdo_map, rpdo_map = create_pdo_map
    servo, _ = connect_to_slave
    servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
    assert len(servo._rpdo_maps) == 1
    assert servo._rpdo_maps[0] == rpdo_map
    assert len(servo._tpdo_maps) == 1
    assert servo._tpdo_maps[0] == tpdo_map
    assert servo.slave.config_func is not None

    servo.map_pdos(1)
    # Check the current PDO mapping
    assert servo.read(servo.TPDO_ASSIGN_REGISTER_SUB_IDX_0, subnode=0) == 1
    assert servo.read(servo.RPDO_ASSIGN_REGISTER_SUB_IDX_0, subnode=0) == 1

    new_rdpo_map = RPDOMap()
    new_tpdo_map = TPDOMap()
    servo.set_pdo_map_to_slave([new_rdpo_map], [new_tpdo_map])
    # Check that the previous mapping was not deleted
    assert servo.read(servo.TPDO_ASSIGN_REGISTER_SUB_IDX_0, subnode=0) == 1
    assert servo.read(servo.RPDO_ASSIGN_REGISTER_SUB_IDX_0, subnode=0) == 1
    # Check that the new PDOMaps were added
    assert len(servo._rpdo_maps) == 2
    assert servo._rpdo_maps[1] == new_rdpo_map
    assert len(servo._tpdo_maps) == 2
    assert servo._tpdo_maps[1] == new_tpdo_map

    # Add same maps again
    servo.set_pdo_map_to_slave([new_rdpo_map, rpdo_map], [new_tpdo_map, tpdo_map])
    # Check that nothing changes
    assert len(servo._rpdo_maps) == 2
    assert servo._rpdo_maps[0] == rpdo_map
    assert servo._rpdo_maps[1] == new_rdpo_map
    assert len(servo._tpdo_maps) == 2
    assert servo._tpdo_maps[0] == tpdo_map
    assert servo._tpdo_maps[1] == new_tpdo_map


@pytest.mark.no_connection
def test_pdo_item_bool():
    register = EthercatRegister(0, 1, RegDtype.BOOL, RegAccess.RW, cyclic=RegCyclicType.RX)
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
    assert rpdo_item.ACCEPTED_CYCLIC == RegCyclicType.RX
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
    assert tpdo_item.ACCEPTED_CYCLIC == RegCyclicType.TX
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
    register = EthercatRegister(0, 1, RegDtype.BOOL, RegAccess.RW, cyclic=RegCyclicType.RX)
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
def test_remove_rpdo_map(connect_to_slave, create_pdo_map):
    _, rpdo_map = create_pdo_map
    servo, _ = connect_to_slave
    servo.set_pdo_map_to_slave([rpdo_map], [])
    assert len(servo._rpdo_maps) > 0
    servo.remove_rpdo_map(rpdo_map)
    assert len(servo._rpdo_maps) == 0
    servo._rpdo_maps.append(rpdo_map)
    servo.remove_rpdo_map(rpdo_map_index=0)
    assert len(servo._rpdo_maps) == 0


@pytest.mark.ethercat
def test_remove_rpdo_map_exceptions(connect_to_slave, create_pdo_map):
    tpdo_map, rpdo_map = create_pdo_map
    servo, _ = connect_to_slave
    servo.set_pdo_map_to_slave([rpdo_map], [])
    with pytest.raises(ValueError):
        servo.remove_rpdo_map()
    with pytest.raises(ValueError):
        servo.remove_rpdo_map(tpdo_map)
    with pytest.raises(IndexError):
        servo.remove_rpdo_map(rpdo_map_index=1)


@pytest.mark.ethercat
def test_remove_tpdo_map(connect_to_slave, create_pdo_map):
    tpdo_map, _ = create_pdo_map
    servo, _ = connect_to_slave
    servo.set_pdo_map_to_slave([], [tpdo_map])
    assert len(servo._tpdo_maps) > 0
    servo.remove_tpdo_map(tpdo_map)
    assert len(servo._tpdo_maps) == 0
    servo._tpdo_maps.append(tpdo_map)
    servo.remove_tpdo_map(tpdo_map_index=0)
    assert len(servo._tpdo_maps) == 0


@pytest.mark.ethercat
def test_remove_tpdo_map_exceptions(connect_to_slave, create_pdo_map):
    _, rpdo_map = create_pdo_map
    servo, _ = connect_to_slave
    servo.set_pdo_map_to_slave([rpdo_map], [])
    with pytest.raises(ValueError):
        servo.remove_rpdo_map()
    with pytest.raises(ValueError):
        servo.remove_tpdo_map(rpdo_map)
    with pytest.raises(IndexError):
        servo.remove_tpdo_map(tpdo_map_index=1)


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
