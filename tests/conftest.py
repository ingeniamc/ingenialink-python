import logging
from pathlib import Path
from typing import Any, Callable, Optional

import pytest
from summit_testing_framework import dynamic_loader
from summit_testing_framework.pytest_helpers.marker_helper import (
    apply_firmware_version_markers_to_items,
)
from virtual_drive.core import VirtualDrive
from virtual_drive.resources import VIRTUAL_DRIVE_CAN_V2_XDF

from ingenialink.dictionary import Interface
from ingenialink.virtual.canopen.network import VirtualCanopenNetwork
from ingenialink.virtual.ethercat.network import VirtualEthercatNetwork
from ingenialink.virtual.ethernet.network import VirtualEthernetNetwork
from tests.ethercat.mock import pysoem_mock_network  # noqa: F401

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
        return "Exception during load_configuration" not in message


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


def pytest_collection_modifyitems(
    session: pytest.Session,  # noqa: ARG001
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Modifies collected tests to skip those that do not meet firmware version restrictions.

    Only runs if --enable_firmware_version_check is passed.

    Args:
        session: pytest session.
        config: pytest configuration.
        items: collected test items.
    """
    apply_firmware_version_markers_to_items(config=config, items=items)


def _create_virtual_drive_connection(
    connect_to_server: Callable[[VirtualDrive], tuple[Any, Any]],
    dictionary: Optional[str] = None,
    protocol: Interface = Interface.VIRTUAL,
) -> tuple[VirtualDrive, Any, Any]:
    server = (
        VirtualDrive(protocol=protocol)
        if dictionary is None
        else VirtualDrive(dictionary_path=dictionary, protocol=protocol)
    )
    server.start()
    try:
        net, servo = connect_to_server(server)
    except Exception:
        if server.is_alive():
            server.stop()
        raise
    return server, net, servo


def _connect_virtual_ethernet(server: VirtualDrive) -> tuple[VirtualEthernetNetwork, Any]:
    net = VirtualEthernetNetwork()
    servo = net.connect_to_slave(server.dictionary_path, server.port)
    return net, servo


def _connect_virtual_ethercat(server: VirtualDrive) -> tuple[Any, Any]:
    net = VirtualEthercatNetwork()
    servo = net.connect_to_slave(1, server.dictionary_path, server.port)
    return net, servo


def _connect_virtual_canopen(server: VirtualDrive) -> tuple[Any, Any]:
    net = VirtualCanopenNetwork()
    servo = net.connect_to_slave(1, server.dictionary_path, server.port)
    return net, servo


@pytest.fixture()
def virtual_drive():
    server, _, virtual_servo = _create_virtual_drive_connection(
        _connect_virtual_ethernet,
    )
    yield server, virtual_servo
    server.stop()


@pytest.fixture()
def virtual_drive_custom_dict():
    servers: list[VirtualDrive] = []

    def connect(dictionary):
        server, net, servo = _create_virtual_drive_connection(
            _connect_virtual_ethernet,
            dictionary,
        )
        servers.append(server)
        return server, net, servo

    yield connect

    for server in servers:
        if server.is_alive():
            server.stop()


@pytest.fixture()
def virtual_drive_ethercat():
    server, _, virtual_servo = _create_virtual_drive_connection(
        _connect_virtual_ethercat,
        protocol=Interface.ECAT,
    )
    yield server, virtual_servo
    server.stop()


@pytest.fixture()
def virtual_drive_canopen():
    server, net, virtual_servo = _create_virtual_drive_connection(
        _connect_virtual_canopen,
        protocol=Interface.CAN,
        dictionary=VIRTUAL_DRIVE_CAN_V2_XDF,
    )
    yield server, net, virtual_servo
    server.stop()


@pytest.fixture()
def virtual_drive_ethercat_custom_dict():
    servers: list[VirtualDrive] = []

    def connect(dictionary):
        server, net, servo = _create_virtual_drive_connection(
            _connect_virtual_ethercat,
            dictionary,
            protocol=Interface.ECAT,
        )
        servers.append(server)
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
