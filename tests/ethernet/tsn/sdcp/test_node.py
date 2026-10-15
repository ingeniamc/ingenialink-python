"""Tests for the SDCP node lifecycle."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ingenialink.enums.node import NodeMode
from ingenialink.ethernet.tsn.sdcp.node import SDCPNode, SDCPNodeDiscovery
from ingenialink.ethernet.tsn.sdcp.servo import SDCPServo
from ingenialink.exceptions import ILError, ILFirmwareLoadError, ILIOError, ILStateError

TARGET = "fe80::1"
INTERFACE = "test-interface"
DICTIONARY_PATH = "test_dictionary.xdf"
RECOVERY_TIMEOUT_S = 2.0
RECOVERY_POLL_INTERVAL_S = 0.01

PROTOCOL_VERSION = 1
SERIAL_NUMBER = 0x12345678
PRODUCT_CODE = 0x90ABCDEF
REVISION_NUMBER = 0x00010002


@pytest.fixture
def application_discovery() -> SDCPNodeDiscovery:
    """Return discovery information for an application-mode node."""
    return SDCPNodeDiscovery(
        target=TARGET,
        interface=INTERFACE,
        protocol_version=PROTOCOL_VERSION,
        serial_number=SERIAL_NUMBER,
        product_code=PRODUCT_CODE,
        revision_number=REVISION_NUMBER,
        mode=NodeMode.APPLICATION,
    )


@pytest.fixture
def bootloader_discovery() -> SDCPNodeDiscovery:
    """Return discovery information for a bootloader-mode node."""
    return SDCPNodeDiscovery(
        target=TARGET,
        interface=INTERFACE,
        protocol_version=PROTOCOL_VERSION,
        serial_number=SERIAL_NUMBER,
        product_code=PRODUCT_CODE,
        revision_number=0,
        mode=NodeMode.BOOTLOADER,
    )


@pytest.fixture
def application_node(application_discovery: SDCPNodeDiscovery) -> SDCPNode:
    """Return an application-mode SDCP node."""
    return SDCPNode(application_discovery)


@pytest.fixture
def bootloader_node(bootloader_discovery: SDCPNodeDiscovery) -> SDCPNode:
    """Return a bootloader-mode SDCP node."""
    return SDCPNode(bootloader_discovery)


@pytest.fixture
def connected_node(
    application_node: SDCPNode,
) -> tuple[SDCPNode, MagicMock]:
    """Return an application-mode node with an associated mocked servo."""
    servo_mock = MagicMock(spec=SDCPServo)

    with patch(
        "ingenialink.ethernet.tsn.sdcp.node.SDCPServo",
        return_value=servo_mock,
    ):
        application_node.connect(DICTIONARY_PATH)

    return application_node, servo_mock


@pytest.fixture
def timeout_mock_factory(mocker):
    """Create a configurable Timeout mock.

    Returns:
        Factory that creates the Timeout context and class mocks.
    """

    def create(has_expired: list[bool]) -> tuple[MagicMock, MagicMock]:
        timeout_mock = MagicMock()
        type(timeout_mock).has_expired = mocker.PropertyMock(
            side_effect=has_expired,
        )
        type(timeout_mock).remaining_time_s = mocker.PropertyMock(
            return_value=RECOVERY_TIMEOUT_S,
        )

        timeout_context = MagicMock()
        timeout_context.__enter__.return_value = timeout_mock

        timeout_class_mock = mocker.patch(
            "ingenialink.ethernet.tsn.sdcp.node.Timeout",
            return_value=timeout_context,
        )

        return timeout_context, timeout_class_mock

    return create


def test_node_exposes_discovery_information(application_node: SDCPNode) -> None:
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
    application_node: SDCPNode,
) -> None:
    """Update mutable discovery information for the same physical drive."""
    updated_discovery = SDCPNodeDiscovery(
        target="fe80::2",
        interface="updated-interface",
        protocol_version=PROTOCOL_VERSION + 1,
        serial_number=SERIAL_NUMBER,
        product_code=PRODUCT_CODE,
        revision_number=0,
        mode=NodeMode.BOOTLOADER,
    )

    application_node.update(updated_discovery)

    assert application_node.target == "fe80::2"
    assert application_node.interface == "updated-interface"
    assert application_node.protocol_version == PROTOCOL_VERSION + 1
    assert application_node.serial_number == SERIAL_NUMBER
    assert application_node.product_code == PRODUCT_CODE
    assert application_node.revision_number == 0
    assert application_node.mode == NodeMode.BOOTLOADER


@pytest.mark.parametrize(
    "serial_number,product_code",
    [
        (SERIAL_NUMBER + 1, PRODUCT_CODE),
        (SERIAL_NUMBER, PRODUCT_CODE + 1),
    ],
)
def test_update_rejects_different_drive_identity(
    application_node: SDCPNode,
    serial_number: int,
    product_code: int,
) -> None:
    """Reject discovery information belonging to another physical drive."""
    discovery = SDCPNodeDiscovery(
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
    connected_node: tuple[SDCPNode, MagicMock],
) -> None:
    """Allow protocol and revision updates that do not affect the connection."""
    node, servo_mock = connected_node
    updated_discovery = SDCPNodeDiscovery(
        target=TARGET,
        interface=INTERFACE,
        protocol_version=PROTOCOL_VERSION + 1,
        serial_number=SERIAL_NUMBER,
        product_code=PRODUCT_CODE,
        revision_number=REVISION_NUMBER + 1,
        mode=NodeMode.APPLICATION,
    )

    node.update(updated_discovery)

    assert node.protocol_version == PROTOCOL_VERSION + 1
    assert node.revision_number == REVISION_NUMBER + 1
    assert node.servo is servo_mock


@pytest.mark.parametrize(
    "updated_discovery",
    [
        SDCPNodeDiscovery(
            target="fe80::2",
            interface=INTERFACE,
            protocol_version=PROTOCOL_VERSION,
            serial_number=SERIAL_NUMBER,
            product_code=PRODUCT_CODE,
            revision_number=REVISION_NUMBER,
            mode=NodeMode.APPLICATION,
        ),
        SDCPNodeDiscovery(
            target=TARGET,
            interface="updated-interface",
            protocol_version=PROTOCOL_VERSION,
            serial_number=SERIAL_NUMBER,
            product_code=PRODUCT_CODE,
            revision_number=REVISION_NUMBER,
            mode=NodeMode.APPLICATION,
        ),
        SDCPNodeDiscovery(
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
    connected_node: tuple[SDCPNode, MagicMock],
    updated_discovery: SDCPNodeDiscovery,
) -> None:
    """Reject target, interface, or mode changes while connected."""
    node, _ = connected_node

    with pytest.raises(
        ILStateError,
        match="Cannot update the target, interface, or mode",
    ):
        node.update(updated_discovery)


def test_connect_creates_and_associates_sdcp_servo(
    application_node: SDCPNode,
) -> None:
    """Create an SDCP servo using the node connection information."""
    servo_mock = MagicMock(spec=SDCPServo)
    disconnect_callback = MagicMock()

    with patch(
        "ingenialink.ethernet.tsn.sdcp.node.SDCPServo",
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


def test_connect_rejects_bootloader_node(bootloader_node: SDCPNode) -> None:
    """Reject application connections while the node is in bootloader mode."""
    with pytest.raises(
        ILStateError,
        match="Cannot connect to an SDCP node in bootloader mode",
    ):
        bootloader_node.connect(DICTIONARY_PATH)


def test_connect_rejects_already_connected_node(
    connected_node: tuple[SDCPNode, MagicMock],
) -> None:
    """Reject creating a second servo association."""
    node, _ = connected_node

    with pytest.raises(
        ILStateError,
        match="The SDCP node is already connected",
    ):
        node.connect(DICTIONARY_PATH)


def test_disconnect_closes_servo_and_clears_association(
    connected_node: tuple[SDCPNode, MagicMock],
) -> None:
    """Disconnect the servo and remove its association from the node."""
    node, servo_mock = connected_node

    node.disconnect()

    servo_mock.disconnect.assert_called_once_with()
    assert node.servo is None
    assert not node.is_connected


def test_disconnect_preserves_association_when_servo_disconnect_fails(
    connected_node: tuple[SDCPNode, MagicMock],
) -> None:
    """Keep the association when the servo cannot be disconnected."""
    node, servo_mock = connected_node
    servo_mock.disconnect.side_effect = ILIOError("disconnect failed")

    with pytest.raises(ILIOError, match="disconnect failed"):
        node.disconnect()

    assert node.servo is servo_mock
    assert node.is_connected


def test_load_firmware_uploads_and_updates_node_after_recovery(
    bootloader_node: SDCPNode,
    bootloader_discovery: SDCPNodeDiscovery,
    timeout_mock_factory,
) -> None:
    """Upload firmware, wait for recovery, and refresh the node information."""
    firmware_file = Path("firmware.lfu")
    callback_progress = MagicMock()
    uploader_mock = MagicMock()
    uploader_context = MagicMock()
    uploader_context.__enter__.return_value = uploader_mock
    timeout_context, timeout_class_mock = timeout_mock_factory(
        has_expired=[False, False, False],
    )
    application_discovery = SDCPNodeDiscovery(
        target=TARGET,
        interface=INTERFACE,
        protocol_version=PROTOCOL_VERSION + 1,
        serial_number=SERIAL_NUMBER,
        product_code=PRODUCT_CODE,
        revision_number=REVISION_NUMBER + 1,
        mode=NodeMode.APPLICATION,
    )

    with (
        patch(
            "ingenialink.ethernet.tsn.sdcp.node.TftpUploader",
            return_value=uploader_context,
        ) as uploader_class_mock,
        patch(
            "ingenialink.ethernet.tsn.sdcp.node.identify_sdcp_node",
            side_effect=[bootloader_discovery, application_discovery],
        ) as identify_mock,
        patch("ingenialink.ethernet.tsn.sdcp.node.time.sleep") as sleep_mock,
    ):
        bootloader_node.load_firmware(
            firmware_file,
            callback_progress=callback_progress,
            recovery_timeout=RECOVERY_TIMEOUT_S,
            recovery_poll_interval=RECOVERY_POLL_INTERVAL_S,
        )

    uploader_class_mock.assert_called_once_with(TARGET, INTERFACE)
    uploader_mock.upload_file.assert_called_once_with(
        firmware_file,
        callback_progress=callback_progress,
    )
    uploader_context.__exit__.assert_called_once()
    timeout_class_mock.assert_called_once_with(RECOVERY_TIMEOUT_S)
    timeout_context.__exit__.assert_called_once()
    assert identify_mock.call_count == 2
    sleep_mock.assert_called_once_with(RECOVERY_POLL_INTERVAL_S)
    assert bootloader_node.target == TARGET
    assert bootloader_node.interface == INTERFACE
    assert bootloader_node.protocol_version == PROTOCOL_VERSION + 1
    assert bootloader_node.revision_number == REVISION_NUMBER + 1
    assert bootloader_node.mode == NodeMode.APPLICATION


def test_load_firmware_retries_if_node_cannot_be_identified(
    bootloader_node: SDCPNode,
    timeout_mock_factory,
) -> None:
    """Retry identification while the node is rebooting."""
    timeout_context, timeout_class_mock = timeout_mock_factory(
        has_expired=[False, False, False],
    )
    application_discovery = SDCPNodeDiscovery(
        target=TARGET,
        interface=INTERFACE,
        protocol_version=PROTOCOL_VERSION + 1,
        serial_number=SERIAL_NUMBER,
        product_code=PRODUCT_CODE,
        revision_number=REVISION_NUMBER + 1,
        mode=NodeMode.APPLICATION,
    )

    with (
        patch("ingenialink.ethernet.tsn.sdcp.node.TftpUploader"),
        patch(
            "ingenialink.ethernet.tsn.sdcp.node.identify_sdcp_node",
            side_effect=[ILError("Node not available"), application_discovery],
        ) as identify_mock,
        patch("ingenialink.ethernet.tsn.sdcp.node.time.sleep") as sleep_mock,
    ):
        bootloader_node.load_firmware(
            "firmware.lfu",
            recovery_timeout=RECOVERY_TIMEOUT_S,
            recovery_poll_interval=RECOVERY_POLL_INTERVAL_S,
        )

    timeout_class_mock.assert_called_once_with(RECOVERY_TIMEOUT_S)
    timeout_context.__exit__.assert_called_once()
    assert identify_mock.call_count == 2
    sleep_mock.assert_called_once_with(RECOVERY_POLL_INTERVAL_S)
    assert bootloader_node.mode == NodeMode.APPLICATION
    assert bootloader_node.revision_number == REVISION_NUMBER + 1


def test_load_firmware_raises_if_node_does_not_recover(
    bootloader_node: SDCPNode,
    bootloader_discovery: SDCPNodeDiscovery,
    timeout_mock_factory,
) -> None:
    """Raise an error if the node does not recover in application mode."""
    uploader_context = MagicMock()
    uploader_context.__enter__.return_value = MagicMock()
    timeout_context, timeout_class_mock = timeout_mock_factory(
        has_expired=[False, True, True],
    )
    error_message = (
        f"SDCP node {bootloader_node.identity} did not recover within {RECOVERY_TIMEOUT_S} seconds."
    )

    with (
        patch(
            "ingenialink.ethernet.tsn.sdcp.node.TftpUploader",
            return_value=uploader_context,
        ),
        patch(
            "ingenialink.ethernet.tsn.sdcp.node.identify_sdcp_node",
            return_value=bootloader_discovery,
        ) as identify_mock,
        patch("ingenialink.ethernet.tsn.sdcp.node.time.sleep") as sleep_mock,
        pytest.raises(ILFirmwareLoadError, match=re.escape(error_message)),
    ):
        bootloader_node.load_firmware(
            "firmware.lfu",
            recovery_timeout=RECOVERY_TIMEOUT_S,
            recovery_poll_interval=RECOVERY_POLL_INTERVAL_S,
        )

    timeout_class_mock.assert_called_once_with(RECOVERY_TIMEOUT_S)
    timeout_context.__exit__.assert_called_once()
    identify_mock.assert_called_once()
    sleep_mock.assert_not_called()
    assert bootloader_node.mode == NodeMode.BOOTLOADER


def test_load_firmware_rejects_application_node(
    application_node: SDCPNode,
) -> None:
    """Reject firmware loading while the node is in application mode."""
    with pytest.raises(
        ILStateError,
        match="Cannot load firmware to an SDCP node in application mode",
    ):
        application_node.load_firmware("firmware.lfu")


def test_load_firmware_rejects_connected_node(
    connected_node: tuple[SDCPNode, MagicMock],
) -> None:
    """Reject firmware loading while a servo is associated."""
    node, _ = connected_node

    with pytest.raises(
        ILStateError,
        match="Cannot load firmware while the SDCP node is connected",
    ):
        node.load_firmware("firmware.lfu")
