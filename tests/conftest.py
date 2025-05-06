import atexit
import itertools
import json
import time
from pathlib import Path

import pytest
import rpyc
from summit_testing_framework import dynamic_loader

from ingenialink.ethercat.network import (
    ETHERCAT_NETWORK_REFERENCES,
    release_network_reference,
)
from ingenialink.virtual.network import VirtualNetwork
from virtual_drive.core import VirtualDrive

pytest_plugins = [
    "summit_testing_framework.pytest_addoptions",
    "summit_testing_framework.setup_fixtures",
]


# Pytest runs with importlib import mode, which means that it will run the tests with the installed
# version of the package. Therefore, modules that are not included in the package cannot be imported
# in the tests.
# The issue is solved by dynamically importing them before the tests start. All modules that should
# be imported and ARE NOT part of the package should be specified here
_DYNAMIC_MODULES_IMPORT = ["tests"]

DEFAULT_PROTOCOL = "no_connection"

ALLOW_PROTOCOLS = [DEFAULT_PROTOCOL, "ethernet", "ethercat", "canopen", "eoe", "multislave"]

SLEEP_BETWEEN_POWER_CYCLE_S = 10


def pytest_sessionstart(session):
    """Loads the modules that are not part of the package if import mode is importlib.

    Args:
        session: session.
    """
    if session.config.option.importmode != "importlib":
        return
    ingenialink_base_path = Path(__file__).parents[1]
    for module_name in _DYNAMIC_MODULES_IMPORT:
        dynamic_loader((ingenialink_base_path / module_name).resolve())


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


@pytest.fixture
def virtual_drive_resources_folder():
    root_folder = Path(__file__).resolve().parent.parent
    return (root_folder / "virtual_drive/resources/").as_posix()


@pytest.fixture
def ethercat_network_teardown():
    """Should be executed for all the tests that do not use `interface_controller` fixture.

    It is used to clear the network reference.
    Many of the tests check that errors are raised, so the reference is not properly cleared."""
    yield
    atexit._run_exitfuncs()
    assert not len(ETHERCAT_NETWORK_REFERENCES)
    # Once atexit is called, the register will be lost, so register the needed functions again
    atexit.register(release_network_reference, None)


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
def get_drive_configuration_from_rack_service(pytestconfig, read_config, connect_to_rack_service):
    client = connect_to_rack_service
    rack_config = client.exposed_get_configuration()
    protocol = pytestconfig.getoption("--protocol")
    protocol_contents = read_config[protocol]
    drive_idx = get_drive_idx_from_rack_config(protocol_contents, rack_config)
    return rack_config.drives[drive_idx]


def get_drive_idx_from_rack_config(protocol_contents, rack_config):
    drive_identifier = protocol_contents["identifier"]
    drive_idx = None
    for idx, drive in enumerate(rack_config.drives):
        if drive_identifier == drive.identifier:
            drive_idx = idx
            break
    if drive_idx is None:
        pytest.fail(f"The drive {drive_identifier} cannot be found on the rack's configuration.")
    return drive_idx
