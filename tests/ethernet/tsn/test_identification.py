"""Tests for TSN node identification."""

from unittest.mock import MagicMock, call, patch

import pytest

from ingenialink.enums.node import NodeMode
from ingenialink.ethernet.tsn.identification import (
    _decode_node_mode,
    identify_tsn_node,
)
from ingenialink.ethernet.tsn.node import TSNNodeDiscovery
from ingenialink.ethernet.tsn.sdcp import (
    SDCPIdentificationRequest,
    SDCPIdentificationResponse,
    SDCPIdentificationResponseError,
    SDCPReadRequest,
    SDCPReadResponse,
    SDCPReadResponseError,
    SDCPWriteResponse,
)
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


def _identification_response() -> SDCPIdentificationResponse:
    """Return a representative SDCP Identification response."""
    return SDCPIdentificationResponse(
        transaction_id=0x0000,
        protocol_version=PROTOCOL_VERSION,
        serial_number=SERIAL_NUMBER,
        product_code=PRODUCT_CODE,
        revision_number=REVISION_NUMBER,
    )


def test_identify_tsn_node_returns_discovery_information(
    connection_mock: MagicMock,
) -> None:
    """Return node discovery information from SDCP responses."""
    connection_mock.request.side_effect = [
        _identification_response(),
        SDCPReadResponse(
            transaction_id=0x0001,
            value=b"\x01\x01",
        ),
    ]
    context = _connection_context(connection_mock)

    with patch(
        "ingenialink.ethernet.tsn.identification.SDCPConnection",
        return_value=context,
    ) as connection_class_mock:
        discovery = identify_tsn_node(
            target=TARGET,
            interface=INTERFACE,
            timeout=TIMEOUT_S,
        )

    assert discovery == TSNNodeDiscovery(
        target=TARGET,
        interface=INTERFACE,
        protocol_version=PROTOCOL_VERSION,
        serial_number=SERIAL_NUMBER,
        product_code=PRODUCT_CODE,
        revision_number=REVISION_NUMBER,
        mode=NodeMode.APPLICATION,
    )
    connection_class_mock.assert_called_once_with(
        TARGET,
        INTERFACE,
        TIMEOUT_S,
    )
    connection_mock.request.assert_has_calls([
        call(SDCPIdentificationRequest(transaction_id=0x0000)),
        call(
            SDCPReadRequest(
                transaction_id=0x0001,
                index=0x1101,
                subindex=0x00,
            )
        ),
    ])
    context.__exit__.assert_called_once()


@pytest.mark.parametrize(
    "data,expected_mode",
    [
        pytest.param(b"\x00\x01", NodeMode.APPLICATION, id="application"),
        pytest.param(b"\x00\x02", NodeMode.BOOTLOADER, id="bootloader"),
    ],
)
def test_decode_node_mode(data: bytes, expected_mode: NodeMode) -> None:
    """Decode the mode while ignoring unrelated status flags."""
    assert _decode_node_mode(data) == expected_mode


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"\x01", id="truncated"),
        pytest.param(b"\x00\x00\x01", id="oversized"),
    ],
)
def test_decode_node_mode_rejects_invalid_size(data: bytes) -> None:
    """Reject Communication Status values that are not UINT16."""
    with pytest.raises(ILIOError, match="Invalid Communication Status size"):
        _decode_node_mode(data)


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"\x00\x00", id="no-mode-active"),
        pytest.param(b"\x00\x03", id="both-modes-active"),
    ],
)
def test_decode_node_mode_rejects_invalid_mode_flags(data: bytes) -> None:
    """Require exactly one operating-mode flag to be active."""
    with pytest.raises(
        ILIOError,
        match="Invalid Communication Status mode flags",
    ):
        _decode_node_mode(data)


def test_identify_tsn_node_raises_identification_error(
    connection_mock: MagicMock,
) -> None:
    """Convert an SDCP Identification error response to ILIOError."""
    connection_mock.request.return_value = SDCPIdentificationResponseError(
        transaction_id=0x0000,
        error_code=0xFFFF0001,
    )
    context = _connection_context(connection_mock)

    with (
        patch(
            "ingenialink.ethernet.tsn.identification.SDCPConnection",
            return_value=context,
        ),
        pytest.raises(
            ILIOError,
            match="SDCP identification failed with error code 0xFFFF0001",
        ),
    ):
        identify_tsn_node(TARGET, INTERFACE)


def test_identify_tsn_node_rejects_unexpected_identification_response(
    connection_mock: MagicMock,
) -> None:
    """Reject a valid non-Identification response."""
    connection_mock.request.return_value = SDCPWriteResponse(
        transaction_id=0x0000,
    )
    context = _connection_context(connection_mock)

    with (
        patch(
            "ingenialink.ethernet.tsn.identification.SDCPConnection",
            return_value=context,
        ),
        pytest.raises(
            ILIOError,
            match="Unexpected SDCP identification response",
        ),
    ):
        identify_tsn_node(TARGET, INTERFACE)


def test_identify_tsn_node_raises_status_read_error(
    connection_mock: MagicMock,
) -> None:
    """Convert a Communication Status Read error to ILIOError."""
    connection_mock.request.side_effect = [
        _identification_response(),
        SDCPReadResponseError(
            transaction_id=0x0001,
            error_code=0xFFFF0002,
        ),
    ]
    context = _connection_context(connection_mock)

    with (
        patch(
            "ingenialink.ethernet.tsn.identification.SDCPConnection",
            return_value=context,
        ),
        pytest.raises(
            ILIOError,
            match=("Could not read the Communication Status object with error code 0xFFFF0002"),
        ),
    ):
        identify_tsn_node(TARGET, INTERFACE)


def test_identify_tsn_node_rejects_unexpected_status_response(
    connection_mock: MagicMock,
) -> None:
    """Reject a valid non-Read response for Communication Status."""
    connection_mock.request.side_effect = [
        _identification_response(),
        SDCPWriteResponse(transaction_id=0x0001),
    ]
    context = _connection_context(connection_mock)

    with (
        patch(
            "ingenialink.ethernet.tsn.identification.SDCPConnection",
            return_value=context,
        ),
        pytest.raises(
            ILIOError,
            match="Unexpected Communication Status response",
        ),
    ):
        identify_tsn_node(TARGET, INTERFACE)
