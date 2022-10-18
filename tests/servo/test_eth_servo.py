from ipaddress import NetmaskValueError

import pytest

from ingenialink.ethernet.servo import MONITORING_DIST_ENABLE, \
    DISTURBANCE_ENABLE
from ingenialink.ethernet.register import REG_DTYPE

MONITORING_CH_DATA_SIZE = 4
MONITORING_NUM_SAMPLES = 100
DISTURBANCE_CH_DATA_SIZE = 4
DISTURBANCE_NUM_SAMPLES = 100


@pytest.fixture()
def create_monitoring(connect_to_slave):
    servo, net = connect_to_slave
    servo.monitoring_disable()
    servo.monitoring_remove_all_mapped_registers()
    registers_key = [
        'CL_POS_SET_POINT_VALUE'
    ]
    subnode = 1
    for idx, key in enumerate(registers_key):
        reg = servo._get_reg(key, subnode=1)
        servo.monitoring_set_mapped_register(
            idx, reg.address, subnode,
            reg.dtype.value, MONITORING_CH_DATA_SIZE
        )
    divisor = 1
    servo.write('MON_DIST_FREQ_DIV', divisor, subnode=0)
    servo.write('MON_CFG_SOC_TYPE', 0, subnode=0)
    servo.write('MON_CFG_WINDOW_SAMP', MONITORING_NUM_SAMPLES, subnode=0)
    yield servo, net
    servo.monitoring_disable()


@pytest.fixture()
def create_disturbance(connect_to_slave):
    servo, net = connect_to_slave
    data = list(range(DISTURBANCE_NUM_SAMPLES))
    servo.disturbance_disable()
    servo.disturbance_remove_all_mapped_registers()
    servo.disturbance_set_mapped_register(0, 0x0020, 1,
                                          REG_DTYPE.S32.value,
                                          DISTURBANCE_CH_DATA_SIZE)
    servo.disturbance_write_data(0, REG_DTYPE.S32, data)
    yield servo, net
    servo.disturbance_disable()


@pytest.mark.ethernet
@pytest.mark.parametrize("ip_address, gateway", [
    ("192.168.2.xx", "192.168.2.1"),
    ("192.168.2.22", "192.168.3.1")
])
def test_change_tcp_ip_parameters_value_error(connect_to_slave,
                                              ip_address, gateway):
    servo, net = connect_to_slave
    with pytest.raises(ValueError):
        servo.change_tcp_ip_parameters(ip_address, "255.255.255.0", gateway)


@pytest.mark.ethernet
def test_change_tcp_ip_parameters_invalid_netmask(connect_to_slave):
    servo, net = connect_to_slave
    with pytest.raises(NetmaskValueError):
        servo.change_tcp_ip_parameters("192.168.2.22", "255.255.255.xx", "192.168.2.1")


@pytest.mark.ethernet
def test_monitoring_enable_disable(connect_to_slave):
    servo, net = connect_to_slave
    servo.monitoring_enable()
    assert servo.read(MONITORING_DIST_ENABLE, subnode=0) == 1
    servo.monitoring_disable()
    assert servo.read(MONITORING_DIST_ENABLE, subnode=0) == 0


@pytest.mark.ethernet
def test_monitoring_remove_data(create_monitoring):
    servo, net = create_monitoring
    servo.monitoring_enable()
    servo.write('MON_CMD_FORCE_TRIGGER', 1, subnode=0)
    assert servo.read('MON_CFG_BYTES_VALUE', subnode=0) > 0
    servo.monitoring_remove_data()
    assert servo.read('MON_CFG_BYTES_VALUE', subnode=0) == 0


@pytest.mark.ethernet
def test_monitoring_map_register(connect_to_slave):
    servo, net = connect_to_slave
    registers_key = [
        'CL_POS_SET_POINT_VALUE',
        'CL_VEL_SET_POINT_VALUE'
    ]
    data_size = 4
    subnode = 1
    for idx, key in enumerate(registers_key):
        reg = servo._get_reg(key, subnode=1)
        servo.monitoring_set_mapped_register(
            idx, reg.address, subnode,
            reg.dtype.value, data_size
        )
    assert servo.monitoring_number_mapped_registers == len(registers_key)
    servo.monitoring_remove_all_mapped_registers()
    assert servo.monitoring_number_mapped_registers == 0


@pytest.mark.ethernet
def test_monitoring_data_size(create_monitoring):
    servo, net = create_monitoring
    servo.monitoring_enable()
    servo.write('MON_CMD_FORCE_TRIGGER', 1, subnode=0)
    assert servo.monitoring_get_bytes_per_block() == \
           MONITORING_CH_DATA_SIZE
    assert servo.monitoring_actual_number_bytes() > 0
    assert servo.monitoring_data_size == \
           MONITORING_CH_DATA_SIZE * MONITORING_NUM_SAMPLES
    servo.monitoring_remove_data()


@pytest.mark.ethernet
def test_disturbance_enable_disable(connect_to_slave):
    servo, net = connect_to_slave
    servo.disturbance_enable()
    assert servo.read(DISTURBANCE_ENABLE, subnode=0) == 1
    servo.disturbance_disable()
    assert servo.read(DISTURBANCE_ENABLE, subnode=0) == 0


@pytest.mark.ethernet
def test_disturbance_remove_data(create_disturbance):
    servo, net = create_disturbance
    servo.disturbance_enable()
    assert servo.read('DIST_CFG_BYTES', subnode=0) == \
           DISTURBANCE_CH_DATA_SIZE * DISTURBANCE_NUM_SAMPLES
    servo.disturbance_remove_data()
    assert servo.read('DIST_CFG_BYTES', subnode=0) == 0


@pytest.mark.ethernet
def test_disturbance_map_register(connect_to_slave):
    servo, net = connect_to_slave
    servo.disturbance_remove_all_mapped_registers()
    registers_key = [
        'CL_POS_SET_POINT_VALUE',
        'CL_VEL_SET_POINT_VALUE'
    ]
    data_size = 4
    subnode = 1
    for idx, key in enumerate(registers_key):
        reg = servo._get_reg(key, subnode=1)
        servo.disturbance_set_mapped_register(
            idx, reg.address, subnode,
            reg.dtype.value, data_size
        )
    assert servo.disturbance_number_mapped_registers == len(registers_key)
    servo.disturbance_remove_all_mapped_registers()
    assert servo.disturbance_number_mapped_registers == 0


@pytest.mark.ethernet
def test_disturbance_data_size(create_disturbance):
    servo, net = create_disturbance
    servo.disturbance_enable()
    assert servo.disturbance_data_size == \
           DISTURBANCE_CH_DATA_SIZE * DISTURBANCE_NUM_SAMPLES
    servo.disturbance_remove_data()
