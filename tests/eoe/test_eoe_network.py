import pytest
import socket
import ipaddress

from ingenialink.ethernet.servo import EthernetServo
from ingenialink.ethernet.network import NET_PROT, NET_STATE
from ingenialink.eoe.network import EoENetwork, EoECommand
from ingenialink.utils._utils import convert_dtype_to_bytes
from ingenialink.register import REG_DTYPE
from ingenialink.constants import (
    EOE_MSG_CMD_SIZE,
    EOE_MSG_NODE_SIZE,
    EOE_MSG_DATA_SIZE,
    EOE_MSG_FRAME_SIZE,
    EOE_MSG_TERMINATOR_SIZE,
)


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
    configured_ip = servo.read("COMMS_ETH_IP", subnode=0)
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


@pytest.mark.parametrize(
    "cmd, subnode, data, dtype",
    [
        (EoECommand.START.value, 0, 10, REG_DTYPE.U16),
        (EoECommand.SCAN.value, 1, 25.5, REG_DTYPE.FLOAT),
        (EoECommand.CONFIG.value, 2, None, None),
    ],
)
@pytest.mark.eoe
def test_eoe_command_msg(cmd, subnode, data, dtype):
    data_bytes = bytes() if data is None else convert_dtype_to_bytes(data, dtype)
    data_filling = b"\x00" * (EOE_MSG_DATA_SIZE - len(data_bytes))
    msg = EoENetwork._build_eoe_command_msg(cmd, subnode, data_bytes)
    cmd_field = msg[:EOE_MSG_CMD_SIZE]
    subnode_field = msg[EOE_MSG_CMD_SIZE : EOE_MSG_NODE_SIZE + EOE_MSG_TERMINATOR_SIZE + 1]
    data_field = msg[-(EOE_MSG_DATA_SIZE + EOE_MSG_TERMINATOR_SIZE) :]
    null_terminator = b"\x00"
    assert len(msg) == EOE_MSG_FRAME_SIZE
    assert cmd_field == cmd.encode("utf-8")
    assert subnode_field == f"{subnode:0{EOE_MSG_NODE_SIZE}d}".encode("utf-8") + null_terminator
    assert data_field == data_bytes + data_filling + null_terminator
