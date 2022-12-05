import json
import pytest

from ingenialink.canopen.network import CanopenNetwork, CAN_DEVICE, CAN_BAUDRATE
from ingenialink.ethernet.network import EthernetNetwork, NET_TRANS_PROT
from ingenialink.ethercat.network import EthercatNetwork
from tests.virtual_drive import VirtualDrive

ALLOW_PROTOCOLS = ["no_connection", "ethernet", "ethercat", "canopen"]


def pytest_addoption(parser):
    parser.addoption("--protocol", action="store", default="no_connection",
                     help=",".join(ALLOW_PROTOCOLS), choices=ALLOW_PROTOCOLS)


@pytest.fixture
def read_config():
    config = 'tests/config.json'
    print('current config file:', config)
    with open(config, "r", encoding='utf-8') as fp:
        contents = json.load(fp)
    return contents


def pytest_collection_modifyitems(config, items):
    protocol = config.getoption("--protocol")
    negate_protocols = [x for x in ALLOW_PROTOCOLS if x != protocol]
    skip_by_protocol = pytest.mark.skip(reason="Protocol does not match")
    for item in items:
        if protocol in item.keywords:
            continue
        for not_protocol in negate_protocols:
            if not_protocol in item.keywords:
                item.add_marker(skip_by_protocol)


def connect_canopen(protocol_contents):
    net = CanopenNetwork(device=CAN_DEVICE(protocol_contents['device']),
                         channel=protocol_contents['channel'],
                         baudrate=CAN_BAUDRATE(protocol_contents['baudrate']))

    servo = net.connect_to_slave(
        target=protocol_contents['node_id'],
        dictionary=protocol_contents['dictionary'],
        eds=protocol_contents['eds'])
    return servo, net


def connect_ethernet(protocol_contents):
    net = EthernetNetwork()

    servo = net.connect_to_slave(
        protocol_contents['ip'],
        protocol_contents['dictionary'],
        protocol_contents['port'])
    return servo, net


def connect_ethercat(protocol_contents):
    net = EthercatNetwork(protocol_contents['ifname'])

    servo = net.connect_to_slave(
        target=protocol_contents['slave'],
        dictionary=protocol_contents['dictionary']
    )
    return servo, net


@pytest.fixture
def connect_to_slave(pytestconfig, read_config):
    servo = None
    net = None
    protocol = pytestconfig.getoption("--protocol")
    protocol_contents = read_config[protocol]
    if protocol == "ethernet":
        servo, net = connect_ethernet(protocol_contents)
    elif protocol == "ethercat":
        servo, net = connect_ethercat(protocol_contents)
    elif protocol == "canopen":
        servo, net = connect_canopen(protocol_contents)

    yield servo, net
    net.disconnect_from_slave(servo)


@pytest.fixture()
def virtual_drive():
    test_ip = "127.0.0.1"
    test_port = 81
    server = VirtualDrive(test_ip, test_port)
    server.start()
    yield server
    server.stop()