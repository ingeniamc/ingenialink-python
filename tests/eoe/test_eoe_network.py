import ipaddress
import socket

import pytest

from ingenialink.eoe.network import EoECommand, EoENetwork
from ingenialink.ethernet.network import NET_PROT
from ingenialink.ethernet.servo import EthernetServo


@pytest.fixture()
def connect(read_config):
    protocol_contents = read_config["eoe"]
    net = EoENetwork(protocol_contents["ifname"])
    servo = net.connect_to_slave(
        slave_id=protocol_contents["slave"],
        ip_address=protocol_contents["ip"],
        dictionary=protocol_contents["dictionary"],
    )
    return servo, net


@pytest.mark.eoe
def test_eoe_connection(connect_to_slave, read_config):
    eoe_service_ip = "127.0.0.1"
    eoe_service_port = 8888
    drive_ip = read_config["eoe"]["ip"]
    servo, net = connect_to_slave
    net_socket = net._eoe_socket
    ip, port = net_socket.getpeername()
    assert servo.is_alive()
    assert len(net.scan_slaves()) > 0
    assert isinstance(servo, EthernetServo)
    assert net._eoe_service_init
    assert net._eoe_service_started
    assert net.protocol == NET_PROT.ETH
    assert net_socket.family == socket.AF_INET
    assert net_socket.type == socket.SOCK_DGRAM
    assert ip == eoe_service_ip
    assert port == eoe_service_port


@pytest.mark.eoe
def test_eoe_connection_wrong_ip_address(read_config):
    protocol_contents = read_config["eoe"]
    net = EoENetwork(protocol_contents["ifname"])
    with pytest.raises(ValueError):
        net.connect_to_slave(
            slave_id=protocol_contents["slave"],
            ip_address="192.168.2.22",
            dictionary=protocol_contents["dictionary"],
        )


@pytest.mark.eoe
def test_eoe_disconnection(connect):
    servo, net = connect
    net.disconnect_from_slave(servo)
    assert not net._eoe_service_init
    assert not net._eoe_service_started
    assert len(net.servos) == 0


@pytest.mark.parametrize(
    "cmd, data",
    [
        (EoECommand.EOE_START, None),
        (EoECommand.SCAN, None),
        (EoECommand.INIT, b"example_ifname"),
        (EoECommand.CONFIG, b"\x01\x00\x16\x03\xa8\xc0\x00\xff\xff\xff"),
    ],
)
@pytest.mark.eoe
def test_eoe_command_msg(cmd, data):
    data_bytes = bytes() if data is None else data
    data_filling = EoENetwork.NULL_TERMINATOR * (EoENetwork.EOE_MSG_DATA_SIZE - len(data_bytes))
    msg = EoENetwork._build_eoe_command_msg(cmd.value, data_bytes)
    cmd_field = msg[: EoENetwork.EOE_MSG_CMD_SIZE]
    data_field = msg[-EoENetwork.EOE_MSG_DATA_SIZE :]
    assert len(msg) == EoENetwork.EOE_MSG_FRAME_SIZE
    assert int.from_bytes(cmd_field, "little") == cmd.value
    assert data_field == data_bytes + data_filling
