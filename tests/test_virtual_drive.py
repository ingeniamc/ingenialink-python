
import time

import pytest

from ingenialink.ethernet.network import EthernetNetwork


MONITORING_CH_DATA_SIZE = 4
MONITORING_NUM_SAMPLES = 100
DISTURBANCE_CH_DATA_SIZE = 4


@pytest.mark.no_connection
def test_connect_to_virtual(virtual_drive, read_config):
    server = virtual_drive
    time.sleep(1)
    net = EthernetNetwork()
    protocol_contents = read_config['ethernet']
    servo = net.connect_to_slave(
        server.ip,
        protocol_contents['dictionary'],
        server.port
    )
    servo.write('CL_AUX_FBK_SENSOR', 4)
    servo.write('DIST_CFG_REG0_MAP', 4, 0)


@pytest.mark.parametrize(
    "reg, value, subnode", 
    [
        ("CL_AUX_FBK_SENSOR", 4, 1),
        ("DIST_CFG_REG0_MAP", 4, 0)
    ]
)
def test_virtual_drive_write_read(virtual_drive, read_config, reg, value, subnode):
    server = virtual_drive

    virtual_net = EthernetNetwork()
    protocol_contents = read_config['ethernet']
    virtual_servo = virtual_net.connect_to_slave(
        server.ip,
        protocol_contents['dictionary'],
        server.port
    )
    
    virtual_servo.write(reg, value, subnode)
    response = virtual_servo.read(reg, subnode)
    assert response == value


@pytest.mark.ethernet
@pytest.mark.parametrize(
    "reg, value, subnode", 
    [
        ("CL_AUX_FBK_SENSOR", 4, 1),
        ("DIST_CFG_REG0_MAP", 4, 0)
    ]
)
def test_virtual_drive_write_read_compare_responses(connect_to_slave, virtual_drive, read_config, reg, value, subnode):
    servo, net = connect_to_slave
    server = virtual_drive

    virtual_net = EthernetNetwork()
    protocol_contents = read_config['ethernet']
    virtual_servo = virtual_net.connect_to_slave(
        server.ip,
        protocol_contents['dictionary'],
        server.port
    )
    
    virtual_response = virtual_servo.write(reg, value, subnode)
    response = servo.write(reg, value, subnode)
    assert response == virtual_response

    response = servo.read(reg, subnode)
    virtual_response = virtual_servo.read(reg, subnode)
    assert response == virtual_response

    new_value = virtual_response + 1
    virtual_servo.write(reg, new_value, subnode)
    saved_value = virtual_servo.read(reg, subnode)
    assert saved_value == new_value


@pytest.mark.no_connection
@pytest.mark.parametrize("divisor", [1, 2])
def test_virtual_monitoring(virtual_drive, read_config, divisor):
    server = virtual_drive

    net = EthernetNetwork()
    protocol_contents = read_config['ethernet']
    servo = net.connect_to_slave(
        server.ip,
        protocol_contents['dictionary'],
        server.port
    )

    servo.monitoring_disable()
    registers_key = [
        'CL_POS_SET_POINT_VALUE',
        'CL_VOL_Q_SET_POINT'
    ]
    subnode = 1
    for idx, key in enumerate(registers_key):
        reg = servo._get_reg(key, subnode=1)
        address = reg.address
        servo.monitoring_set_mapped_register(
            idx, address, subnode,
            reg.dtype.value, MONITORING_CH_DATA_SIZE
        )
    
    servo.write('MON_DIST_FREQ_DIV', divisor, subnode=0)
    servo.write('MON_CFG_SOC_TYPE', 1, subnode=0)
    servo.write('MON_CFG_WINDOW_SAMP', MONITORING_NUM_SAMPLES, subnode=0)
    
    servo.monitoring_enable()
    servo.write('MON_CMD_FORCE_TRIGGER', 1, subnode=0)
    time.sleep(0.1)
    servo.monitoring_disable()

    servo.monitoring_read_data()

    for idx, key in enumerate(registers_key):
        reg = servo._get_reg(key, subnode=1)
        address = reg.address
        subnode = reg.subnode
        data = servo.monitoring_channel_data(idx)
        expected_data = [
            subnode + address + i for i in range(0, MONITORING_NUM_SAMPLES*divisor, divisor)
        ]
        assert data == expected_data


@pytest.mark.no_connection
def test_virtual_disturbance(virtual_drive, read_config):
    server = virtual_drive

    net = EthernetNetwork()
    protocol_contents = read_config['ethernet']
    servo = net.connect_to_slave(
        server.ip,
        protocol_contents['dictionary'],
        server.port
    )
    servo.disturbance_disable()
    servo.disturbance_remove_all_mapped_registers()

    registers_key = [
        'CL_POS_SET_POINT_VALUE',
        'CL_VOL_Q_SET_POINT'
    ]
    subnode = 1
    dtypes = []
    data_arr = [] 
    for idx, key in enumerate(registers_key):
        reg = servo._get_reg(key, subnode=1)
        address = reg.address
        servo.disturbance_set_mapped_register(
            idx, address, subnode,
            reg.dtype.value, 4
        )
        dtypes.append(reg.dtype)
        data_arr.append([0, -1, 2, 3])
    
    channels = list(range(len(registers_key)))
    servo.disturbance_write_data(channels, dtypes, data_arr)
    servo.disturbance_enable()
    
    for channel in range(len(registers_key)):
        assert server._VirtualDrive__disturbance.channels[channel]["data"] == data_arr[channel]
