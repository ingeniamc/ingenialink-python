import itertools
import logging
from pathlib import Path

import pytest
from summit_testing_framework import dynamic_loader

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


class SuppressSpecificLogs(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        # Suppress logs containing this specific message
        return not (
            "Exception during load_configuration" in message
            or record.name == "ingenialink.configuration_file"
        )


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):  # noqa: ARG001
    logging.getLogger("ingenialink.servo").addFilter(SuppressSpecificLogs())


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
def virtual_drive_resources_folder():
    root_folder = Path(__file__).resolve().parent.parent
    return (root_folder / "virtual_drive/resources/").as_posix()


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
def get_drive_configuration_from_rack_service(setup_descriptor, rs_client):
    if setup_descriptor.rack_drive_idx is None:
        raise ValueError
    return rs_client.configuration.drives[setup_descriptor.rack_drive_idx]
