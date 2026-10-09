"""Tests for SDCP node identification."""

from unittest.mock import MagicMock, patch

import pytest

from ingenialink.enums.node import NodeMode
from ingenialink.ethernet.tsn.sdcp import (
    SDCPDeserializer,
    SDCPDeviceMode,
    SDCPIdentificationRequest,
    SDCPIdentificationResponse,
    SDCPIdentificationResponseError,
    SDCPProfileFlags,
    SDCPReadResponse,
    SDCPReadResponseError,
    SDCPWriteResponse,
)
from ingenialink.ethernet.tsn.sdcp.discovery import SDCPNodeDiscovery
from ingenialink.ethernet.tsn.sdcp.identification import identify_sdcp_node
from ingenialink.exceptions import ILIOError

TARGET = "fe80::1"
INTERFACE = "test-interface"
TIMEOUT_S = 2.0

PROTOCOL_VERSION = 1
SERIAL_NUMBER = 0x12345678
PRODUCT_CODE = 0x90ABCDEF
REVISION_NUMBER = 0x00010002


@pytest.fixture
def connection_mock() -> MagicMock:
    """Return a mocked SDCP connection."""
    return MagicMock()


def _connection_context(connection_mock: MagicMock) -> MagicMock:
    """Return an SDCP connection context yielding the supplied mock."""
    context = MagicMock()
    context.__enter__.return_value = connection_mock
    return context


def _identification_response(
    device_mode: SDCPDeviceMode = SDCPDeviceMode.APPLICATION,
) -> SDCPIdentificationResponse:
    """Return a representative SDCP Identification response."""
    return SDCPIdentificationResponse(
        transaction_id=0x0000,
        protocol_version=PROTOCOL_VERSION,
        profile_flags=SDCPProfileFlags.SECURITY | SDCPProfileFlags.REALTIME,
        device_mode=device_mode,
        serial_number=SERIAL_NUMBER,
        product_code=PRODUCT_CODE,
        revision_number=REVISION_NUMBER,
    )


@pytest.mark.parametrize(
    "device_mode, expected_mode",
    [
        (SDCPDeviceMode.APPLICATION, NodeMode.APPLICATION),
        (SDCPDeviceMode.BOOTLOADER, NodeMode.BOOTLOADER),
    ],
)
def test_identify_tsn_node_returns_discovery_information(
    connection_mock: MagicMock, device_mode: SDCPDeviceMode, expected_mode: NodeMode
) -> None:
    """Return node discovery information from SDCP responses."""
    connection_mock.request.return_value = _identification_response(device_mode)
    context = _connection_context(connection_mock)

    with patch(
        "ingenialink.ethernet.tsn.sdcp.identification.SDCPConnection",
        return_value=context,
    ) as connection_class_mock:
        discovery = identify_sdcp_node(
            target=TARGET,
            interface=INTERFACE,
            timeout=TIMEOUT_S,
        )

    assert discovery == SDCPNodeDiscovery(
        target=TARGET,
        interface=INTERFACE,
        protocol_version=PROTOCOL_VERSION,
        serial_number=SERIAL_NUMBER,
        product_code=PRODUCT_CODE,
        revision_number=REVISION_NUMBER,
        mode=expected_mode,
    )
    connection_class_mock.assert_called_once_with(
        TARGET,
        INTERFACE,
        TIMEOUT_S,
    )
    connection_mock.request.assert_called_once_with(
        SDCPIdentificationRequest(transaction_id=0x0000)
    )
    context.__exit__.assert_called_once()


def test_identify_tsn_node_raises_identification_error(
    connection_mock: MagicMock,
) -> None:
    """Convert an SDCP Identification error response to ILIOError."""
    connection_mock.request.return_value = SDCPIdentificationResponseError(
        transaction_id=0x0000,
        error_code=0x0001,
    )
    context = _connection_context(connection_mock)

    with (
        patch(
            "ingenialink.ethernet.tsn.sdcp.identification.SDCPConnection",
            return_value=context,
        ),
        pytest.raises(
            ILIOError,
            match="SDCP identification failed with error code 0x0001",
        ),
    ):
        identify_sdcp_node(TARGET, INTERFACE)


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(bytes(SDCPReadResponse(0x0000, b"\x12\x34")), id="read-response"),
        pytest.param(bytes(SDCPWriteResponse(0x0000)), id="write-response"),
        pytest.param(bytes(SDCPReadResponseError(0x0000, 0x0001)), id="read-error-response"),
        pytest.param(bytes(SDCPIdentificationRequest(0x0000)), id="request-without-reply"),
    ],
)
def test_identify_tsn_node_rejects_unexpected_identification_response(
    connection_mock: MagicMock, response: bytes
) -> None:
    """Reject mismatched opcodes, errors, and request-form Identify frames."""
    connection_mock.request.return_value = SDCPDeserializer.deserialize(response)
    context = _connection_context(connection_mock)

    with (
        patch(
            "ingenialink.ethernet.tsn.sdcp.identification.SDCPConnection",
            return_value=context,
        ),
        pytest.raises(
            ILIOError,
            match="Unexpected SDCP identification response",
        ),
    ):
        identify_sdcp_node(TARGET, INTERFACE)
