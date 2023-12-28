import pytest

from ingenialink.ethercat.pdo import PDOMap, PDOType, PDOMapItem, PDOMapper
from ingenialink.ethercat.dictionary import EthercatDictionary
from ingenialink.register import Register
from ingenialink.canopen.servo import CanopenServo

TPDO_REGISTERS = ["CL_POS_FBK_VALUE", "CL_VEL_FBK_VALUE"]
RPDO_REGISTERS = ["CL_POS_SET_POINT_VALUE", "CL_VEL_SET_POINT_VALUE"]


def dummy_callback(pdo_map_item):
    pass


@pytest.fixture()
def create_pdo_map(read_config):
    dictionary = read_config["ethercat"]["dictionary"]
    ethercat_dictionary = EthercatDictionary(dictionary)
    pdo_map = PDOMap(ethercat_dictionary)

    for tpdo_register in TPDO_REGISTERS:
        pdo_map.add_register(tpdo_register, dummy_callback, PDOType.TPDO)
    for rpdo_register in RPDO_REGISTERS:
        pdo_map.add_register(rpdo_register, dummy_callback, PDOType.RPDO)

    return pdo_map


@pytest.mark.no_connection
def test_pdo_map(create_pdo_map):
    pdo_map = create_pdo_map

    assert len(pdo_map.rpdo_registers) == len(RPDO_REGISTERS)
    assert len(pdo_map.tpdo_registers) == len(TPDO_REGISTERS)

    assert all(isinstance(pdo_map_item, PDOMapItem) for pdo_map_item in pdo_map.rpdo_registers)
    assert all(isinstance(pdo_map_item, PDOMapItem) for pdo_map_item in pdo_map.tpdo_registers)

    assert all(
        isinstance(pdo_map_item.register, Register) for pdo_map_item in pdo_map.rpdo_registers
    )
    assert all(
        isinstance(pdo_map_item.register, Register) for pdo_map_item in pdo_map.tpdo_registers
    )


@pytest.mark.ethercat
def test_pdo_mapper_reset(connect_to_slave, create_pdo_map):
    servo, net = connect_to_slave
    pdo_map = create_pdo_map
    pdo_mapper = PDOMapper(servo, pdo_map)
    pdo_mapper.reset_rpdo_mapping()
    pdo_mapper.reset_tpdo_mapping()
    num_mapped_tpdo = servo.read(PDOMapper.TPDO_MAP_REGISTER_SUB_IDX_0)
    assert num_mapped_tpdo == 0
    num_mapped_rpdo = servo.read(PDOMapper.RPDO_MAP_REGISTER_SUB_IDX_0)
    assert num_mapped_rpdo == 0


@pytest.mark.ethercat
def test_pdo_mapper_set_slave_mapping(connect_to_slave, create_pdo_map):
    servo, net = connect_to_slave
    pdo_map = create_pdo_map
    pdo_mapper = PDOMapper(servo, pdo_map)
    pdo_mapper.set_slave_mapping()
    num_mapped_tpdo = servo.read(PDOMapper.TPDO_MAP_REGISTER_SUB_IDX_0)
    assert num_mapped_tpdo == len(TPDO_REGISTERS)
    num_mapped_rpdo = servo.read(PDOMapper.RPDO_MAP_REGISTER_SUB_IDX_0)
    assert num_mapped_rpdo == len(RPDO_REGISTERS)


@pytest.mark.no_connection
@pytest.mark.parametrize(
    "uid, expected_value",
    [("CL_POS_FBK_VALUE", 0x20300020), ("CL_VEL_FBK_VALUE", 0x20310020)],
)
def test_pdo_mapper_map_register(read_config, uid, expected_value):
    dictionary = read_config["ethercat"]["dictionary"]
    ethercat_dictionary = EthercatDictionary(dictionary)
    register = ethercat_dictionary.registers(1)[uid]
    assert expected_value.to_bytes(4, "little") == PDOMapper.map_register(register)


@pytest.mark.no_connection
def test_pdo_mapper_map_register_exception():
    with pytest.raises(NotImplementedError):
        PDOMapper.map_register(CanopenServo.MONITORING_DATA)


@pytest.mark.ethercat
def test_map_rpdo(connect_to_slave, create_pdo_map):
    servo, net = connect_to_slave
    pdo_map = create_pdo_map
    pdo_mapper = PDOMapper(servo, pdo_map)
    pdo_mapper.reset_rpdo_mapping()
    pdo_mapper.map_rpdo()
    value = servo._read_raw(PDOMapper.RPDO_ASSIGN_REGISTER_SUB_IDX_0, complete_access=True)
    assert int.to_bytes(0x1600, 2, "little") == value[2:4]


@pytest.mark.ethercat
def test_map_tpdo(connect_to_slave, create_pdo_map):
    servo, net = connect_to_slave
    pdo_map = create_pdo_map
    pdo_mapper = PDOMapper(servo, pdo_map)
    pdo_mapper.reset_tpdo_mapping()
    pdo_mapper.map_tpdo()
    value = servo._read_raw(PDOMapper.TPDO_ASSIGN_REGISTER_SUB_IDX_0, complete_access=True)
    assert int.to_bytes(0x1A00, 2, "little") == value[2:4]
