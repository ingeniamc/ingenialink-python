import pytest
import socket
import ipaddress

from ingenialink.ethernet.servo import EthernetServo
from ingenialink.ethernet.network import NET_PROT, NET_STATE
from ingenialink.eoe.network import EoENetwork


@pytest.fixture()
def connect(read_config):
    protocol_contents = read_config['eoe']
    net = EoENetwork(protocol_contents['ifname'])
    servo = net.connect_to_slave(
        slave_id=protocol_contents['slave'],
        ip_address=protocol_contents['ip'],
        dictionary=protocol_contents['dictionary']
    )
    return servo, net


@pytest.mark.eoe
def test_eoe_connection(connect_to_slave, read_config):
    eoe_service_ip = "127.0.0.1"
    eoe_service_port = 8888
    drive_ip = read_config['eoe']['ip']
    servo, net = connect_to_slave
    net_socket = net._eoe_socket
    ip, port = net_socket.getpeername()
    configured_ip = servo.read('COMMS_ETH_IP', subnode=0)
    assert net.scan_slaves() > 0
    assert drive_ip == str(ipaddress.ip_address(configured_ip))
    assert isinstance(servo, EthernetServo)
    assert net.status == NET_STATE.CONNECTED
    assert net.protocol == NET_PROT.ETH
    assert net_socket.family == socket.AF_INET
    assert net_socket.type == socket.SOCK_DGRAM
    assert ip == eoe_service_ip
    assert port == eoe_service_port


@pytest.mark.eoe
def test_eoe_disconnection(connect):
    servo, net = connect
    net.disconnect_from_slave(servo)
    assert net.status == NET_STATE.DISCONNECTED
    assert len(net.servos) == 0
    assert net._eoe_socket._closed

