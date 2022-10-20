import socket

import pytest

from ingenialink.ethernet.network import EthernetNetwork, NET_TRANS_PROT, \
    NET_PROT, NET_STATE


@pytest.fixture()
def connect(read_config):
    net = EthernetNetwork()
    protocol_contents = read_config['ethernet']
    servo = net.connect_to_slave(
        protocol_contents['ip'],
        protocol_contents['dictionary'],
        protocol_contents['port'],
        NET_TRANS_PROT[protocol_contents['protocol']]
    )
    return servo, net


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
    family = net.socket.family
    config_protocol = NET_TRANS_PROT[read_config['ethernet']['protocol']]
    ip, port = net.socket.getpeername()
    socket_protocol = {
        socket.SOCK_DGRAM: NET_TRANS_PROT.UDP,
        socket.SOCK_STREAM: NET_TRANS_PROT.TCP
    }
    assert net.status == NET_STATE.CONNECTED
    assert net.protocol == NET_PROT.ETH
    assert family == socket.AF_INET
    assert config_protocol == socket_protocol[net.socket.type]
    assert ip == read_config['ethernet']['ip']
    assert port == read_config['ethernet']['port']


@pytest.mark.ethernet
def test_ethernet_disconnection(connect):
    servo, net = connect
    net.disconnect_from_slave(servo)
    assert net.status == NET_STATE.DISCONNECTED
    assert len(net.servos) == 0
    assert net.socket._closed



