import json
import time

from bitarray import bitarray

try:
    import pysoem
except ImportError:
    pass
import pytest

from ingenialink import EthercatNetwork
from ingenialink.dictionary import Interface
from ingenialink.enums.register import REG_ACCESS, REG_DTYPE
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.exceptions import ILError
from ingenialink.pdo import RPDOMap, RPDOMapItem, TPDOMap, TPDOMapItem
from ingenialink.register import Register
from ingenialink.servo import DictionaryFactory
from ingenialink.utils._utils import convert_dtype_to_bytes, dtype_length_bits

TPDO_REGISTERS = ["CL_POS_FBK_VALUE", "CL_VEL_FBK_VALUE"]
RPDO_REGISTERS = ["CL_POS_SET_POINT_VALUE", "CL_VEL_SET_POINT_VALUE"]
SUBNODE = 1


@pytest.fixture()
def open_dictionary(read_config):
    dictionary = read_config["ethercat"]["dictionary"]
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
    assert str(exc_info.value) == "Incorrect cyclic. It should be CYCLIC_RX, obtained: CYCLIC_TX"


@pytest.mark.no_connection
def test_tpdo_item_wrong_cyclic(open_dictionary):
    ethercat_dictionary = open_dictionary
    register = ethercat_dictionary.registers(SUBNODE)[RPDO_REGISTERS[0]]
    with pytest.raises(ILError) as exc_info:
        TPDOMapItem(register)
    assert str(exc_info.value) == "Incorrect cyclic. It should be CYCLIC_TX, obtained: CYCLIC_RX"


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
def test_pdo_item_register_mapping(read_config, uid, expected_value):
    dictionary = read_config["ethercat"]["dictionary"]
    ethercat_dictionary = DictionaryFactory.create_dictionary(dictionary, Interface.ECAT)
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

    assert servo.read(EthercatServo.TPDO_ASSIGN_REGISTER_SUB_IDX_0) == 0
    assert servo.read(EthercatServo.RPDO_ASSIGN_REGISTER_SUB_IDX_0) == 0

    servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
    servo.map_pdos(1)

    assert servo.read(EthercatServo.TPDO_ASSIGN_REGISTER_SUB_IDX_0) == 1
    assert len(servo._tpdo_maps) == 1
    assert tpdo_map.map_register_index == EthercatServo.TPDO_MAP_REGISTER_SUB_IDX_0[0].idx
    assert tpdo_map.map_register_index_bytes == tpdo_map.map_register_index.to_bytes(4, "little")
    assert servo.read(EthercatServo.TPDO_MAP_REGISTER_SUB_IDX_0[0]) == len(TPDO_REGISTERS)
    value = servo._read_raw(EthercatServo.TPDO_ASSIGN_REGISTER_SUB_IDX_0, complete_access=True)
    assert int.to_bytes(0x1A00, 2, "little") == value[2:4]

    assert servo.read(EthercatServo.RPDO_ASSIGN_REGISTER_SUB_IDX_0) == 1
    assert len(servo._rpdo_maps) == 1
    assert rpdo_map.map_register_index == EthercatServo.RPDO_MAP_REGISTER_SUB_IDX_0[0].idx
    assert rpdo_map.map_register_index_bytes == rpdo_map.map_register_index.to_bytes(4, "little")
    assert servo.read(EthercatServo.RPDO_MAP_REGISTER_SUB_IDX_0[0]) == len(RPDO_REGISTERS)
    value = servo._read_raw(EthercatServo.RPDO_ASSIGN_REGISTER_SUB_IDX_0, complete_access=True)
    assert int.to_bytes(0x1600, 2, "little") == value[2:4]


@pytest.mark.ethercat
def test_servo_reset_pdos(connect_to_slave, create_pdo_map):
    tpdo_map, rpdo_map = create_pdo_map
    servo, _ = connect_to_slave

    servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
    servo.map_pdos(1)

    assert servo.read(EthercatServo.TPDO_ASSIGN_REGISTER_SUB_IDX_0) == 1
    assert servo.read(EthercatServo.RPDO_ASSIGN_REGISTER_SUB_IDX_0) == 1
    assert len(servo._rpdo_maps) == 1
    assert len(servo._tpdo_maps) == 1

    servo.reset_tpdo_mapping()
    servo.reset_rpdo_mapping()

    assert servo.read(EthercatServo.TPDO_ASSIGN_REGISTER_SUB_IDX_0) == 0
    assert servo.read(EthercatServo.RPDO_ASSIGN_REGISTER_SUB_IDX_0) == 0
    assert len(servo._rpdo_maps) == 0
    assert len(servo._tpdo_maps) == 0


@pytest.mark.ethercat
def test_pdo_example(read_config, script_runner):
    protocol_contents = read_config["ethercat"]
    ifname = protocol_contents["ifname"]
    dictionary = protocol_contents["dictionary"]
    script_path = "examples/ethercat/process_data_objects.py"
    result = script_runner.run(
        script_path, f"-ifname={ifname}", f"-dict={dictionary}", "-auto_stop"
    )
    assert result.returncode == 0


@pytest.fixture
def connect_to_all_slave(pytestconfig):
    protocol = pytestconfig.getoption("--protocol")
    if protocol != "ethercat":
        raise AssertionError("Wrong protocol")
    config = "tests/config.json"
    with open(config, "r", encoding="utf-8") as fp:
        contents = json.load(fp)
    protocol_contents = contents[protocol]
    servos = []
    net = EthercatNetwork(protocol_contents[0]["ifname"])
    for slave_content in protocol_contents:
        servos.append(net.connect_to_slave(slave_content["slave"], slave_content["dictionary"]))
    yield servos, net
    for servo in servos:
        net.disconnect_from_slave(servo)


@pytest.mark.ethercat
def test_start_stop_pdo(connect_to_all_slave):
    servos, net = connect_to_all_slave
    operation_mode_uid = "DRV_OP_CMD"
    rpdo_registers = [operation_mode_uid]
    default_operation_mode = 1
    current_operation_mode = {}
    new_operation_mode = {}
    for index, servo in enumerate(servos):
        current_operation_mode[index] = servo.read(operation_mode_uid)
        new_operation_mode[index] = default_operation_mode
        if current_operation_mode[index] == default_operation_mode:
            new_operation_mode[index] += 1
        rpdo_map = RPDOMap()
        tpdo_map = TPDOMap()
        for tpdo_register in TPDO_REGISTERS:
            register = servo.dictionary.registers(SUBNODE)[tpdo_register]
            tpdo_map.add_registers(register)
        for rpdo_register in rpdo_registers:
            register = servo.dictionary.registers(SUBNODE)[rpdo_register]
            rpdo_map.add_registers(register)
        for item in rpdo_map.items:
            item.value = new_operation_mode[index]
        servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
        net._ecat_master.read_state()
        assert servo.slave.state_check(pysoem.PREOP_STATE) == pysoem.PREOP_STATE
    net.start_pdos()
    net._ecat_master.read_state()
    start_time = time.time()
    timeout = 1
    while time.time() < start_time + timeout:
        net.send_receive_processdata()
    for servo in servos:
        assert servo.slave.state_check(pysoem.OP_STATE) == pysoem.OP_STATE
    net.stop_pdos()
    net._ecat_master.read_state()
    for index, servo in enumerate(servos):
        assert servo.slave.state_check(pysoem.PREOP_STATE) == pysoem.PREOP_STATE
        # Check that RPDOs are being received by the slave
        assert servo._rpdo_maps[0].items[0].value == servo.read(operation_mode_uid)
        # Restore the previous operation mode
        servo.write(operation_mode_uid, current_operation_mode[index])
        # Check that TPDOs are being sent by the slave
        # TODO: Confirm this approx is needed in INGK-839
        assert pytest.approx(servo._tpdo_maps[0].items[0].value, abs=2) == servo.read(
            TPDO_REGISTERS[0]
        )


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
    servo, net = connect_to_slave
    servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
    assert servo._rpdo_maps[0] == rpdo_map
    assert servo._tpdo_maps[0] == tpdo_map
    assert servo.slave.config_func is not None


@pytest.mark.no_connection
def test_pdo_item_bool():
    register = EthercatRegister(0, 1, REG_DTYPE.BOOL, REG_ACCESS.RW, cyclic="CYCLIC_RX")
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
def test_map_pdo_with_bools(open_dictionary):
    ethercat_dictionary = open_dictionary
    register = ethercat_dictionary.registers(SUBNODE)[RPDO_REGISTERS[0]]
    item1 = RPDOMapItem(register)
    item2 = RPDOMapItem(register, size_bits=4)
    register = EthercatRegister(0, 1, REG_DTYPE.BOOL, REG_ACCESS.RW, cyclic="CYCLIC_RX")
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
