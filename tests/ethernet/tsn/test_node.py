"""Tests for the TSN node lifecycle."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ingenialink.enums.node import NodeMode
from ingenialink.ethernet.tsn.node import TSNNode, TSNNodeDiscovery
from ingenialink.ethernet.tsn.servo import TSNServo
from ingenialink.exceptions import ILIOError, ILStateError

TARGET = "fe80::1"
INTERFACE = "test-interface"
DICTIONARY_PATH = "test_dictionary.xdf"

PROTOCOL_VERSION = 1
SERIAL_NUMBER = 0x12345678
PRODUCT_CODE = 0x90ABCDEF
REVISION_NUMBER = 0x00010002


@pytest.fixture
def application_discovery() -> TSNNodeDiscovery:
    """Return discovery information for an application-mode node."""
    return TSNNodeDiscovery(
        target=TARGET,
        interface=INTERFACE,
        protocol_version=PROTOCOL_VERSION,
        serial_number=SERIAL_NUMBER,
        product_code=PRODUCT_CODE,
        revision_number=REVISION_NUMBER,
        mode=NodeMode.APPLICATION,
    )


@pytest.fixture
def bootloader_discovery() -> TSNNodeDiscovery:
    """Return discovery information for a bootloader-mode node."""
    return TSNNodeDiscovery(
        target=TARGET,
        interface=INTERFACE,
        protocol_version=PROTOCOL_VERSION,
        serial_number=SERIAL_NUMBER,
        product_code=PRODUCT_CODE,
        revision_number=0,
        mode=NodeMode.BOOTLOADER,
    )


@pytest.fixture
def application_node(application_discovery: TSNNodeDiscovery) -> TSNNode:
    """Return an application-mode TSN node."""
    return TSNNode(application_discovery)


@pytest.fixture
def bootloader_node(bootloader_discovery: TSNNodeDiscovery) -> TSNNode:
    """Return a bootloader-mode TSN node."""
    return TSNNode(bootloader_discovery)


def test_node_exposes_discovery_information(application_node: TSNNode) -> None:
    """Expose the information from the latest discovery."""
    assert application_node.target == TARGET
    assert application_node.interface == INTERFACE
    assert application_node.protocol_version == PROTOCOL_VERSION
    assert application_node.serial_number == SERIAL_NUMBER
    assert application_node.product_code == PRODUCT_CODE
    assert application_node.revision_number == REVISION_NUMBER
    assert application_node.mode == NodeMode.APPLICATION
    assert application_node.servo is None
    assert not application_node.is_connected


def test_update_replaces_mutable_discovery_information(
    application_node: TSNNode,
) -> None:
    """Update mutable discovery information for the same physical drive."""
    updated_discovery = TSNNodeDiscovery(
        target="fe80::2",
        interface="updated-interface",
        protocol_version=PROTOCOL_VERSION + 1,
        serial_number=SERIAL_NUMBER,
        product_code=PRODUCT_CODE,
        revision_number=REVISION_NUMBER + 1,
        mode=NodeMode.BOOTLOADER,
    )

    application_node.update(updated_discovery)

    assert application_node.target == "fe80::2"
    assert application_node.interface == "updated-interface"
    assert application_node.protocol_version == PROTOCOL_VERSION + 1
    assert application_node.serial_number == SERIAL_NUMBER
    assert application_node.product_code == PRODUCT_CODE
    assert application_node.revision_number == REVISION_NUMBER + 1
    assert application_node.mode == NodeMode.BOOTLOADER


@pytest.mark.parametrize(
    "serial_number,product_code",
    [
        (SERIAL_NUMBER + 1, PRODUCT_CODE),
        (SERIAL_NUMBER, PRODUCT_CODE + 1),
    ],
)
def test_update_rejects_different_drive_identity(
    application_node: TSNNode,
    serial_number: int,
    product_code: int,
) -> None:
    """Reject discovery information belonging to another physical drive."""
    discovery = TSNNodeDiscovery(
        target=TARGET,
        interface=INTERFACE,
        protocol_version=PROTOCOL_VERSION,
        serial_number=serial_number,
        product_code=product_code,
        revision_number=REVISION_NUMBER,
        mode=NodeMode.APPLICATION,
    )

    with pytest.raises(ValueError, match="different drive identity"):
        application_node.update(discovery)


def test_update_allows_firmware_information_change_while_connected(
    application_node: TSNNode,
) -> None:
    """Allow protocol and revision updates that do not affect the connection."""
    servo_mock = MagicMock(spec=TSNServo)
    updated_discovery = TSNNodeDiscovery(
        target=TARGET,
        interface=INTERFACE,
        protocol_version=PROTOCOL_VERSION + 1,
        serial_number=SERIAL_NUMBER,
        product_code=PRODUCT_CODE,
        revision_number=REVISION_NUMBER + 1,
        mode=NodeMode.APPLICATION,
    )

    with patch(
        "ingenialink.ethernet.tsn.node.TSNServo",
        return_value=servo_mock,
    ):
        application_node.connect(DICTIONARY_PATH)

    application_node.update(updated_discovery)

    assert application_node.protocol_version == PROTOCOL_VERSION + 1
    assert application_node.revision_number == REVISION_NUMBER + 1
    assert application_node.servo is servo_mock


@pytest.mark.parametrize(
    "updated_discovery",
    [
        TSNNodeDiscovery(
            target="fe80::2",
            interface=INTERFACE,
            protocol_version=PROTOCOL_VERSION,
            serial_number=SERIAL_NUMBER,
            product_code=PRODUCT_CODE,
            revision_number=REVISION_NUMBER,
            mode=NodeMode.APPLICATION,
        ),
        TSNNodeDiscovery(
            target=TARGET,
            interface="updated-interface",
            protocol_version=PROTOCOL_VERSION,
            serial_number=SERIAL_NUMBER,
            product_code=PRODUCT_CODE,
            revision_number=REVISION_NUMBER,
            mode=NodeMode.APPLICATION,
        ),
        TSNNodeDiscovery(
            target=TARGET,
            interface=INTERFACE,
            protocol_version=PROTOCOL_VERSION,
            serial_number=SERIAL_NUMBER,
            product_code=PRODUCT_CODE,
            revision_number=0,
            mode=NodeMode.BOOTLOADER,
        ),
    ],
    ids=["target", "interface", "mode"],
)
def test_update_rejects_connection_context_change_while_connected(
    application_node: TSNNode,
    updated_discovery: TSNNodeDiscovery,
) -> None:
    """Reject endpoint or mode changes while a servo is associated."""
    servo_mock = MagicMock(spec=TSNServo)

    with patch(
        "ingenialink.ethernet.tsn.node.TSNServo",
        return_value=servo_mock,
    ):
        application_node.connect(DICTIONARY_PATH)

    with pytest.raises(
        ILStateError,
        match="Cannot update the target, interface, or mode",
    ):
        application_node.update(updated_discovery)


def test_connect_creates_and_associates_tsn_servo(
    application_node: TSNNode,
) -> None:
    """Create a TSN servo using the node endpoint and connection options."""
    servo_mock = MagicMock(spec=TSNServo)
    disconnect_callback = MagicMock()

    with patch(
        "ingenialink.ethernet.tsn.node.TSNServo",
        return_value=servo_mock,
    ) as servo_class_mock:
        servo = application_node.connect(
            dictionary_path=DICTIONARY_PATH,
            connection_timeout=2.0,
            servo_status_listener=True,
            disconnect_callback=disconnect_callback,
        )

    assert servo is servo_mock
    assert application_node.servo is servo_mock
    assert application_node.is_connected
    servo_class_mock.assert_called_once_with(
        target=TARGET,
        interface=INTERFACE,
        dictionary_path=DICTIONARY_PATH,
        connection_timeout=2.0,
        servo_status_listener=True,
        disconnect_callback=disconnect_callback,
    )


def test_connect_rejects_bootloader_node(bootloader_node: TSNNode) -> None:
    """Reject application connections while the node is in bootloader mode."""
    with pytest.raises(
        ILStateError,
        match="Cannot connect to a TSN node in bootloader mode",
    ):
        bootloader_node.connect(DICTIONARY_PATH)


def test_connect_rejects_already_connected_node(
    application_node: TSNNode,
) -> None:
    """Reject creating a second servo association."""
    servo_mock = MagicMock(spec=TSNServo)

    with patch(
        "ingenialink.ethernet.tsn.node.TSNServo",
        return_value=servo_mock,
    ):
        application_node.connect(DICTIONARY_PATH)

        with pytest.raises(
            ILStateError,
            match="The TSN node is already connected",
        ):
            application_node.connect(DICTIONARY_PATH)


def test_disconnect_closes_servo_and_clears_association(
    application_node: TSNNode,
) -> None:
    """Disconnect the servo and remove its association from the node."""
    servo_mock = MagicMock(spec=TSNServo)

    with patch(
        "ingenialink.ethernet.tsn.node.TSNServo",
        return_value=servo_mock,
    ):
        application_node.connect(DICTIONARY_PATH)

    application_node.disconnect()

    servo_mock.disconnect.assert_called_once_with()
    assert application_node.servo is None
    assert not application_node.is_connected


def test_disconnect_preserves_association_when_servo_disconnect_fails(
    application_node: TSNNode,
) -> None:
    """Keep the association when the servo cannot be disconnected."""
    servo_mock = MagicMock(spec=TSNServo)
    servo_mock.disconnect.side_effect = ILIOError("disconnect failed")

    with patch(
        "ingenialink.ethernet.tsn.node.TSNServo",
        return_value=servo_mock,
    ):
        application_node.connect(DICTIONARY_PATH)

    with pytest.raises(ILIOError, match="disconnect failed"):
        application_node.disconnect()

    assert application_node.servo is servo_mock
    assert application_node.is_connected


def test_load_firmware_uses_tftp_uploader(bootloader_node: TSNNode) -> None:
    """Upload firmware using the node IPv6 target and interface."""
    firmware_file = Path("firmware.lfu")
    callback_progress = MagicMock()
    uploader_mock = MagicMock()
    uploader_context = MagicMock()
    uploader_context.__enter__.return_value = uploader_mock

    with patch(
        "ingenialink.ethernet.tsn.node.TftpUploader",
        return_value=uploader_context,
    ) as uploader_class_mock:
        bootloader_node.load_firmware(
            firmware_file,
            callback_progress=callback_progress,
        )

    uploader_class_mock.assert_called_once_with(TARGET, INTERFACE)
    uploader_mock.upload_file.assert_called_once_with(
        firmware_file,
        callback_progress=callback_progress,
    )
    uploader_context.__exit__.assert_called_once()


def test_load_firmware_rejects_application_node(
    application_node: TSNNode,
) -> None:
    """Reject firmware loading while the node is in application mode."""
    with pytest.raises(
        ILStateError,
        match="Cannot load firmware to a TSN node in application mode",
    ):
        application_node.load_firmware("firmware.lfu")


def test_load_firmware_rejects_connected_node(
    application_node: TSNNode,
) -> None:
    """Reject firmware loading while a servo is associated."""
    servo_mock = MagicMock(spec=TSNServo)

    with patch(
        "ingenialink.ethernet.tsn.node.TSNServo",
        return_value=servo_mock,
    ):
        application_node.connect(DICTIONARY_PATH)

    with pytest.raises(
        ILStateError,
        match="Cannot load firmware while the TSN node is connected",
    ):
        application_node.load_firmware("firmware.lfu")
