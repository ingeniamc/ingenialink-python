import time

try:
    import pysoem
except ImportError:
    pass
import pytest

from ingenialink.enums.register import REG_DTYPE
from ingenialink.ethercat.dictionary import EthercatDictionary
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.exceptions import ILError
from ingenialink.pdo import RPDOMap, RPDOMapItem, TPDOMap, TPDOMapItem
from ingenialink.register import Register
from ingenialink.utils._utils import convert_dtype_to_bytes, dtype_value

TPDO_REGISTERS = ["CL_POS_FBK_VALUE", "CL_VEL_FBK_VALUE"]
RPDO_REGISTERS = ["CL_POS_SET_POINT_VALUE", "CL_VEL_SET_POINT_VALUE"]
SUBNODE = 1


@pytest.fixture()
def open_dictionary(read_config):
    dictionary = read_config["ethercat"]["dictionary"]
    ethercat_dictionary = EthercatDictionary(dictionary)
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
    assert rpdo_item.size == dtype_value[rpdo_item.register.dtype][0]

    with pytest.raises(ILError) as exc_info:
        rpdo_item.value
    assert str(exc_info.value) == "Raw data is empty."

    rpdo_item.value = 15
    assert rpdo_item.value == 15


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
    assert tpdo_item.size == dtype_value[tpdo_item.register.dtype][0]

    with pytest.raises(ILError) as exc_info:
        tpdo_item.value
    assert str(exc_info.value) == "Raw data is empty."

    with pytest.raises(AttributeError):
        tpdo_item.value = 15

    tpdo_item.raw_data = convert_dtype_to_bytes(15, REG_DTYPE.U16)
    assert tpdo_item.value == 15


@pytest.mark.no_connection
@pytest.mark.parametrize(
    "uid, expected_value",
    [("CL_POS_FBK_VALUE", 0x20300020), ("CL_VEL_FBK_VALUE", 0x20310020)],
)
def test_pdo_item_register_mapping(read_config, uid, expected_value):
    dictionary = read_config["ethercat"]["dictionary"]
    ethercat_dictionary = EthercatDictionary(dictionary)
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
        pdo_map_item.size == dtype_value[pdo_map_item.register.dtype][0]
        for pdo_map_item in tpdo_map.items
    )
    assert all(
        pdo_map_item.size == dtype_value[pdo_map_item.register.dtype][0]
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

    servo.set_mapping_in_slave([rpdo_map], [tpdo_map])
    servo.map_pdos(1)

    assert servo.read(EthercatServo.TPDO_ASSIGN_REGISTER_SUB_IDX_0) == 1
    assert len(servo._tpdo_maps) == 1
    assert tpdo_map.map_register_index == EthercatServo.TPDO_MAP_REGISTER_SUB_IDX_0[0].idx
    assert servo.read(EthercatServo.TPDO_MAP_REGISTER_SUB_IDX_0[0]) == len(TPDO_REGISTERS)
    value = servo._read_raw(EthercatServo.TPDO_ASSIGN_REGISTER_SUB_IDX_0, complete_access=True)
    assert int.to_bytes(0x1A00, 2, "little") == value[2:4]

    assert servo.read(EthercatServo.RPDO_ASSIGN_REGISTER_SUB_IDX_0) == 1
    assert len(servo._rpdo_maps) == 1
    assert rpdo_map.map_register_index == EthercatServo.RPDO_MAP_REGISTER_SUB_IDX_0[0].idx
    assert servo.read(EthercatServo.RPDO_MAP_REGISTER_SUB_IDX_0[0]) == len(RPDO_REGISTERS)
    value = servo._read_raw(EthercatServo.RPDO_ASSIGN_REGISTER_SUB_IDX_0, complete_access=True)
    assert int.to_bytes(0x1600, 2, "little") == value[2:4]


@pytest.mark.ethercat
def test_servo_reset_pdos(connect_to_slave, create_pdo_map):
    tpdo_map, rpdo_map = create_pdo_map
    servo, _ = connect_to_slave

    servo.set_mapping_in_slave([rpdo_map], [tpdo_map])
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


# Remove skip in INGK-786
@pytest.mark.skip("Skip after implementing INGK-786")
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
    assert result.stderr == ""


@pytest.mark.ethercat
def test_start_stop_pdo(connect_to_slave, create_pdo_map):
    tpdo_map, rpdo_map = create_pdo_map
    servo, net = connect_to_slave
    for item in rpdo_map.items:
        item.value = 0
    servo.set_mapping_in_slave([rpdo_map], [tpdo_map])
    net._ecat_master.read_state()
    assert servo.slave.state_check(pysoem.PREOP_STATE) == pysoem.PREOP_STATE
    net.start_pdos()
    for _ in range(5):
        net._ecat_master.send_processdata()
        net._ecat_master.receive_processdata(
            timeout=net.ECAT_PROCESSDATA_TIMEOUT_NS
        )
        time.sleep(0.01)
    net._ecat_master.read_state()
    assert servo.slave.state_check(pysoem.OP_STATE) == pysoem.OP_STATE
    net.stop_pdos()
    net._ecat_master.read_state()
    assert servo.slave.state_check(pysoem.PREOP_STATE) == pysoem.PREOP_STATE


@pytest.mark.ethercat
def test_start_pdo_error_rpod_values_not_set(connect_to_slave, create_pdo_map):
    tpdo_map, rpdo_map = create_pdo_map
    servo, net = connect_to_slave
    servo.set_mapping_in_slave([rpdo_map], [tpdo_map])
    with pytest.raises(ILError):
        net.start_pdos()


@pytest.mark.ethercat
def test_set_mapping_in_slave(connect_to_slave, create_pdo_map):
    tpdo_map, rpdo_map = create_pdo_map
    servo, net = connect_to_slave
    servo.set_mapping_in_slave([rpdo_map], [tpdo_map])
    assert servo._rpdo_maps[0] == rpdo_map
    assert servo._tpdo_maps[0] == tpdo_map
    assert servo.slave.config_func is not None
