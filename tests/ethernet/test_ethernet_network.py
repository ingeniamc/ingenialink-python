import time
import socket

import pytest

from ingenialink.ethernet.network import EthernetNetwork, \
    NET_PROT, NET_STATE, NET_DEV_EVT
from ingenialink.network import NET_TRANS_PROT
from ingenialink.exceptions import ILFirmwareLoadError


@pytest.fixture()
def connect(read_config):
    net = EthernetNetwork()
    protocol_contents = read_config['ethernet']
    servo = net.connect_to_slave(
        protocol_contents['ip'],
        protocol_contents['dictionary'],
        protocol_contents['port']
    )
    return servo, net


@pytest.mark.ethernet
def test_connect_to_slave(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None
    assert len(net.servos) == 1
    fw_version = servo.read('DRV_ID_SOFTWARE_VERSION')
    assert fw_version is not None and fw_version != ''


@pytest.mark.ethernet
def test_scan_slaves(read_config):
    # TODO: Not implemented
    # net = EthernetNetwork()
    # slaves = net.scan_slaves()
    # assert len(slaves) > 0
    pass


@pytest.mark.ethernet
def test_ethernet_connection(connect_to_slave, read_config):
    servo, net = connect_to_slave
    family = servo.socket.family
    ip, port = servo.socket.getpeername()
    assert net._get_servo_state(read_config['ethernet']['ip']) == NET_STATE.CONNECTED
    assert net.protocol == NET_PROT.ETH
    assert family == socket.AF_INET
    assert servo.socket.type == socket.SOCK_DGRAM
    assert ip == read_config['ethernet']['ip']
    assert port == read_config['ethernet']['port']


@pytest.mark.ethernet
def test_ethernet_disconnection(connect, read_config):
    servo, net = connect
    net.disconnect_from_slave(servo)
    assert net._get_servo_state(read_config['ethernet']['ip']) == NET_STATE.DISCONNECTED
    assert len(net.servos) == 0
    assert servo.socket._closed


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


@pytest.mark.ethernet
@pytest.mark.parametrize(
    "reg, value, subnode", 
    [
        ("CL_AUX_FBK_SENSOR", 4, 1),
        ("DIST_CFG_REG0_MAP", 4, 0)
    ]
)
def test_virtual_drive_write_read(connect_to_slave, virtual_drive, read_config, reg, value, subnode):
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
def test_load_firmware_file_not_found():
    virtual_net = EthernetNetwork()
    with pytest.raises(FileNotFoundError):
        virtual_net.load_firmware("no_file")


@pytest.mark.no_connection
def test_load_firmware_no_connection(read_config):
    protocol_contents = read_config['ethernet']
    virtual_net = EthernetNetwork()
    with pytest.raises(ILFirmwareLoadError):
        virtual_net.load_firmware(protocol_contents["fw_file"], target="127.0.0.1", ftp_user="", ftp_pwd="")


@pytest.mark.skip
@pytest.mark.no_connection
def test_load_firmware_wrong_user_pwd():
    # TODO: implement
    pass

@pytest.mark.skip
@pytest.mark.no_connection
def test_load_firmware_error_during_loading():
    # TODO: implement
    pass


@pytest.mark.no_connection
def test_net_status_listener_connection(virtual_drive, read_config):
    server = virtual_drive
    net = EthernetNetwork()
    protocol_contents = read_config['ethernet']
    status_list = []
    net.connect_to_slave(server.ip, dictionary=protocol_contents["dictionary"])

    status_list = []
    net.subscribe_to_status(server.ip, status_list.append)
    # Emulate a disconnection. TODO: disconnect from the virtual drive
    net._set_servo_state(server.ip, NET_STATE.DISCONNECTED)
    net.start_status_listener()
    time.sleep(2)
    net.stop_status_listener()

    assert len(status_list) == 1
    assert status_list[0] == NET_DEV_EVT.ADDED

    
@pytest.mark.skip
@pytest.mark.no_connection
def test_net_status_listener_disconnection():
    # TODO: implement
    pass


@pytest.mark.no_connection
def test_unsubscribe_from_status(virtual_drive, read_config):
    server = virtual_drive
    net = EthernetNetwork()
    protocol_contents = read_config['ethernet']

    status_list = []
    net.connect_to_slave(server.ip, dictionary=protocol_contents["dictionary"])

    status_list = []
    net.subscribe_to_status(server.ip, status_list.append)
    net.unsubscribe_from_status(server.ip, status_list.append)

    # Emulate a disconnection. TODO: disconnect from the virtual drive
    net._set_servo_state(server.ip, NET_STATE.DISCONNECTED)
    net.start_status_listener()
    time.sleep(2)
    net.stop_status_listener()

    assert len(status_list) == 0