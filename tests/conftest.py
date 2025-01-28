import itertools
import json

import pytest
import rpyc

from ingenialink.canopen.network import CAN_BAUDRATE, CAN_DEVICE, CanopenNetwork
from ingenialink.eoe.network import EoENetwork
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.virtual.network import VirtualNetwork
from virtual_drive.core import VirtualDrive

DEFAULT_PROTOCOL = "no_connection"

ALLOW_PROTOCOLS = [DEFAULT_PROTOCOL, "ethernet", "ethercat", "canopen", "eoe"]


def pytest_addoption(parser):
    parser.addoption(
        "--protocol",
        action="store",
        default=DEFAULT_PROTOCOL,
        help=",".join(ALLOW_PROTOCOLS),
        choices=ALLOW_PROTOCOLS,
    )
    parser.addoption("--slave", type=int, default=0, help="Slave index in config.json")
    parser.addoption(
        "--job_name",
        action="store",
        default="ingenialink - Unknown",
        help="Name of the executing job. Will be set to rack service to have more info of the logs",
    )


@pytest.fixture(scope="session")
def read_config(request):
    config = "tests/config.json"
    with open(config, encoding="utf-8") as fp:
        contents = json.load(fp)
    slave = request.config.getoption("--slave")
    for key in contents:
        if isinstance(contents[key], list) and len(contents[key]) > slave:
            contents[key] = contents[key][slave]
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
    net = CanopenNetwork(
        device=CAN_DEVICE(protocol_contents["device"]),
        channel=protocol_contents["channel"],
        baudrate=CAN_BAUDRATE(protocol_contents["baudrate"]),
    )

    servo = net.connect_to_slave(
        target=protocol_contents["node_id"],
        dictionary=protocol_contents["dictionary"],
    )
    return servo, net


def connect_ethernet(protocol_contents):
    net = EthernetNetwork()

    servo = net.connect_to_slave(
        protocol_contents["ip"], protocol_contents["dictionary"], protocol_contents["port"]
    )
    return servo, net


def connect_ethercat(protocol_contents):
    net = EthercatNetwork(protocol_contents["ifname"])

    servo = net.connect_to_slave(
        protocol_contents["slave"], protocol_contents["dictionary"], net_status_listener=True
    )
    return servo, net


def connect_eoe(protocol_contents):
    net = EoENetwork(protocol_contents["ifname"])

    servo = net.connect_to_slave(
        slave_id=protocol_contents["slave"],
        ip_address=protocol_contents["ip"],
        dictionary=protocol_contents["dictionary"],
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
    elif protocol == "canopen":
        servo, net = connect_canopen(protocol_contents)
    elif protocol == "eoe":
        servo, net = connect_eoe(protocol_contents)
    elif protocol == "ethercat":
        servo, net = connect_ethercat(protocol_contents)

    filename = read_config[protocol]["load_config_file"]
    servo.load_configuration(filename)

    yield servo, net
    net.disconnect_from_slave(servo)


@pytest.fixture()
def virtual_drive():
    server = VirtualDrive(81)
    server.start()
    net = VirtualNetwork()
    virtual_servo = net.connect_to_slave(server.dictionary_path, server.port)
    yield server, virtual_servo
    server.stop()


@pytest.fixture()
def virtual_drive_custom_dict():
    servers: list[VirtualDrive] = []
    next_port = itertools.count(81)

    def connect(dictionary):
        server = VirtualDrive(next(next_port), dictionary)
        servers.append(server)
        server.start()
        net = VirtualNetwork()
        servo = net.connect_to_slave(server.dictionary_path, server.port)
        return server, net, servo

    yield connect

    for server in servers:
        if server.is_alive():
            server.stop()


@pytest.fixture(scope="session")
def connect_to_rack_service(request):
    rack_service_port = 33810
    client = rpyc.connect("localhost", rack_service_port, config={"sync_request_timeout": None})
    client.root.set_job_name(request.config.getoption("--job_name"))
    yield client.root
    client.close()


@pytest.fixture(scope="session")
def get_configuration_from_rack_service(pytestconfig, read_config, connect_to_rack_service):
    protocol = pytestconfig.getoption("--protocol")
    protocol_contents = read_config[protocol]
    drive_identifier = protocol_contents["identifier"]
    client = connect_to_rack_service
    config = client.exposed_get_configuration()
    drive_idx = None
    for idx, drive in enumerate(config.drives):
        if drive_identifier == drive.identifier:
            drive_idx = idx
            break
    if drive_idx is None:
        pytest.fail(f"The drive {drive_identifier} cannot be found on the rack's configuration.")
    return drive_idx, config.drives


@pytest.fixture(scope="session", autouse=True)
def load_firmware(pytestconfig, read_config, request):
    protocol = pytestconfig.getoption("--protocol")
    if protocol == DEFAULT_PROTOCOL:
        return
    protocol_contents = read_config[protocol]
    drive_idx, config = request.getfixturevalue("get_configuration_from_rack_service")
    drive = config[drive_idx]
    client = request.getfixturevalue("connect_to_rack_service")
    client.exposed_firmware_load(
        drive_idx, protocol_contents["fw_file"], drive.product_code, drive.serial_number
    )
