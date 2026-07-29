"""Tests for SDCP transactions over UDP/IPv6."""

import socket
from unittest.mock import MagicMock, patch

import pytest

from ingenialink.ethernet.tsn.sdcp.connection import SDCPConnection
from ingenialink.ethernet.tsn.sdcp.messages import (
    SDCPReadRequest,
    SDCPReadResponse,
    SDCPReadResponseError,
    SDCPUnknownFrame,
)
from ingenialink.exceptions import ILIOError, ILTimeoutError

DEVICE_ADDRESS = "fe80::1234"
INTERFACE = "test-interface"
INTERFACE_INDEX = 3
TIMEOUT_S = 1.0
TRANSACTION_ID = 0x1234


@pytest.fixture
def socket_mock() -> MagicMock:
    """Return a mocked UDP/IPv6 socket."""
    return MagicMock(spec=socket.socket)


@pytest.fixture
def connection(socket_mock: MagicMock) -> SDCPConnection:
    """Create an SDCP connection without opening a real socket.

    Returns:
        SDCP connection with a mocked socket.
    """
    with (
        patch(
            "ingenialink.ethernet.tsn.sdcp.connection.get_interface_index",
            return_value=INTERFACE_INDEX,
        ),
        patch(
            "ingenialink.ethernet.tsn.sdcp.connection.socket.socket",
            return_value=socket_mock,
        ),
    ):
        return SDCPConnection(
            address=DEVICE_ADDRESS,
            interface=INTERFACE,
            timeout=TIMEOUT_S,
        )


def _read_request(
    transaction_id: int = TRANSACTION_ID,
) -> SDCPReadRequest:
    """Return a representative SDCP request."""
    return SDCPReadRequest(
        transaction_id=transaction_id,
        index=0x1000,
        subindex=0x00,
    )


def test_init_converts_socket_creation_error() -> None:
    """Convert socket creation failures to ILIOError."""
    with (
        patch(
            "ingenialink.ethernet.tsn.sdcp.connection.get_interface_index",
            return_value=INTERFACE_INDEX,
        ),
        patch(
            "ingenialink.ethernet.tsn.sdcp.connection.socket.socket",
            side_effect=OSError("creation failure"),
        ),
        pytest.raises(
            ILIOError,
            match="Could not create the SDCP socket",
        ),
    ):
        SDCPConnection(
            address=DEVICE_ADDRESS,
            interface=INTERFACE,
            timeout=TIMEOUT_S,
        )


def test_init_closes_socket_when_connection_fails(
    socket_mock: MagicMock,
) -> None:
    """Close the socket when connecting to the device fails."""
    socket_mock.connect.side_effect = OSError("connection failure")

    with (
        patch(
            "ingenialink.ethernet.tsn.sdcp.connection.get_interface_index",
            return_value=INTERFACE_INDEX,
        ),
        patch(
            "ingenialink.ethernet.tsn.sdcp.connection.socket.socket",
            return_value=socket_mock,
        ),
        pytest.raises(
            ILIOError,
            match="Could not connect to SDCP device",
        ),
    ):
        SDCPConnection(
            address=DEVICE_ADDRESS,
            interface=INTERFACE,
            timeout=TIMEOUT_S,
        )

    socket_mock.close.assert_called_once_with()


def test_request_returns_valid_response(
    connection: SDCPConnection,
    socket_mock: MagicMock,
) -> None:
    """Send a request and return its validated response."""
    request_message = _read_request()
    response_message = SDCPReadResponse(
        transaction_id=TRANSACTION_ID,
        value=b"\x12\x34",
    )
    socket_mock.recv.return_value = bytes(response_message)

    result = connection.request(request_message)

    assert result == response_message
    socket_mock.send.assert_called_once_with(bytes(request_message))
    socket_mock.recv.assert_called_once_with(connection._MAX_RESPONSE_SIZE)


def test_request_returns_valid_error_response(
    connection: SDCPConnection,
    socket_mock: MagicMock,
) -> None:
    """Return operation errors as valid SDCP responses."""
    request_message = _read_request()
    response_message = SDCPReadResponseError(
        transaction_id=TRANSACTION_ID,
        error_code=0xFFFF0001,
    )
    socket_mock.recv.return_value = bytes(response_message)

    assert connection.request(request_message) == response_message


def test_request_rejects_request_frame_received_as_response(
    connection: SDCPConnection,
    socket_mock: MagicMock,
) -> None:
    """Reject a request frame received where a response is expected."""
    request_message = _read_request()
    socket_mock.recv.return_value = bytes(request_message)

    with pytest.raises(
        ILIOError,
        match="Unexpected SDCP frame received as response",
    ):
        connection.request(request_message)


def test_request_rejects_unknown_frame(
    connection: SDCPConnection,
    socket_mock: MagicMock,
) -> None:
    """Reject an SDCP frame with an unknown opcode or flags."""
    request_message = _read_request()
    unknown_frame = SDCPUnknownFrame(
        transaction_id=TRANSACTION_ID,
        opcode=0xFF,
        flags=0x80,
        payload=b"\x12\x34",
    )
    socket_mock.recv.return_value = bytes(unknown_frame)

    with pytest.raises(
        ILIOError,
        match="Unexpected SDCP frame received as response",
    ):
        connection.request(request_message)


def test_request_rejects_transaction_id_mismatch(
    connection: SDCPConnection,
    socket_mock: MagicMock,
) -> None:
    """Require the response transaction ID to match the request."""
    request_message = _read_request()
    response_message = SDCPReadResponse(
        transaction_id=TRANSACTION_ID + 1,
        value=b"\x12\x34",
    )
    socket_mock.recv.return_value = bytes(response_message)

    with pytest.raises(
        ILIOError,
        match=("SDCP transaction ID mismatch: expected 0x1234, received 0x1235"),
    ):
        connection.request(request_message)


def test_request_wraps_malformed_response_error(
    connection: SDCPConnection,
    socket_mock: MagicMock,
) -> None:
    """Convert malformed SDCP responses to ILIOError."""
    socket_mock.recv.return_value = b"\x02\x01"

    with pytest.raises(
        ILIOError,
        match="Invalid SDCP response",
    ):
        connection.request(_read_request())


def test_request_converts_socket_timeout(
    connection: SDCPConnection,
    socket_mock: MagicMock,
) -> None:
    """Convert socket timeouts to ILTimeoutError."""
    socket_mock.recv.side_effect = socket.timeout

    with pytest.raises(
        ILTimeoutError,
        match="Timed out waiting for an SDCP response",
    ):
        connection.request(_read_request())


def test_request_converts_socket_error(
    connection: SDCPConnection,
    socket_mock: MagicMock,
) -> None:
    """Convert socket communication failures to ILIOError."""
    socket_mock.send.side_effect = OSError("socket failure")

    with pytest.raises(
        ILIOError,
        match="SDCP communication",
    ):
        connection.request(_read_request())


def test_request_rejects_closed_connection(
    connection: SDCPConnection,
    socket_mock: MagicMock,
) -> None:
    """Reject requests after the connection has been closed."""
    connection.close()
    socket_mock.reset_mock()

    with pytest.raises(
        ILIOError,
        match="The SDCP connection is closed",
    ):
        connection.request(_read_request())

    socket_mock.send.assert_not_called()


def test_close_is_idempotent(
    connection: SDCPConnection,
    socket_mock: MagicMock,
) -> None:
    """Close the underlying socket only once."""
    connection.close()
    connection.close()

    socket_mock.close.assert_called_once_with()


def test_close_converts_socket_error(
    connection: SDCPConnection,
    socket_mock: MagicMock,
) -> None:
    """Convert socket close failures and mark the connection closed."""
    socket_mock.close.side_effect = OSError("close failure")

    with pytest.raises(
        ILIOError,
        match="Could not close the SDCP socket",
    ):
        connection.close()

    assert connection._closed is True


def test_context_manager_closes_connection(
    connection: SDCPConnection,
    socket_mock: MagicMock,
) -> None:
    """Close the connection when leaving its context."""
    with connection as entered_connection:
        assert entered_connection is connection

    socket_mock.close.assert_called_once_with()
