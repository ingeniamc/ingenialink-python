"""Tests for SDCP message serialization and deserialization."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

from ingenialink.utils.sdcp import (
    SDCPErrorResponse,
    SDCPEventSubscriptionRequest,
    SDCPIdentificationRequest,
    SDCPIdentificationResponse,
    SDCPIdentificationResponseError,
    SDCPPeriodicSubscriptionRequest,
    SDCPReadRequest,
    SDCPReadResponse,
    SDCPReadResponseError,
    SDCPSerializer,
    SDCPSubscribeResponse,
    SDCPSubscribeResponseError,
    SDCPUnknownFrame,
    SDCPUnsubscribeRequest,
    SDCPUnsubscribeResponse,
    SDCPUnsubscribeResponseError,
    SDCPWriteRequest,
    SDCPWriteResponse,
    SDCPWriteResponseError,
    _SDCPFields,
    _SDCPPayloadReader,
)


def test_serialize_identification_request() -> None:
    """Serialize the Identification request from the SDCP protocol specification."""
    assert SDCPSerializer.serialize_identification_request(0x1234) == bytes.fromhex("01001234")


def test_serialize_read_request() -> None:
    """Serialize the Read request from the SDCP protocol specification."""
    assert SDCPSerializer.serialize_read_request(0x1234, 0x26E6, 0x00) == bytes.fromhex(
        "0200123426E600"
    )


def test_serialize_write_request() -> None:
    """Serialize the Write request from the SDCP protocol specification."""
    frame = SDCPSerializer.serialize_write_request(0x1234, 0x2821, 0x00, bytes.fromhex("42C80000"))

    assert frame == bytes.fromhex("0300123428210042C80000")


def test_serialize_subscription_requests() -> None:
    """Serialize both subscription request layouts from the specification."""
    periodic_frame = SDCPSerializer.serialize_periodic_subscription_request(
        0x1234, 0x2031, 0x00, 100, 2000
    )
    event_frame = SDCPSerializer.serialize_event_subscription_request(0x1234, 0x2E4D, 0x00, 2000)

    assert periodic_frame == bytes.fromhex("0400123420310001006407D0")
    assert event_frame == bytes.fromhex("040012342E4D000207D0")


def test_serialize_unsubscribe_request() -> None:
    """Serialize the Unsubscribe request using its dedicated opcode."""
    assert SDCPSerializer.serialize_unsubscribe_request(0x1234, 0x5678) == bytes.fromhex(
        "050012345678"
    )


def test_serialize_responses() -> None:
    """Serialize successful and error responses with their dedicated builders."""
    success_frame = SDCPSerializer.serialize_success_response(
        0x02, 0x1234, bytes.fromhex("12345678")
    )
    error_frame = SDCPSerializer.serialize_error_response(0x02, 0x1234, 0x06020000)

    assert success_frame == bytes.fromhex("0201123412345678")
    assert error_frame == bytes.fromhex("0203123406020000")


def test_payload_reader_tracks_offset_and_remaining_bytes() -> None:
    """Read fixed-width and raw payload values sequentially."""
    reader = _SDCPPayloadReader(bytes.fromhex("123456ABCD"))

    assert reader.read_uint(_SDCPFields.TRANSACTION_ID) == 0x1234
    assert reader.read_bytes(1) == b"V"
    assert reader.read_remaining() == bytes.fromhex("ABCD")
    reader.ensure_end()


def test_payload_reader_rejects_incomplete_fixed_width_values() -> None:
    """Reject fixed-width reads when the payload is too short."""
    with pytest.raises(ValueError):
        _SDCPPayloadReader(b"\x12").read_uint(_SDCPFields.TRANSACTION_ID)


def test_payload_reader_reports_trailing_byte_count() -> None:
    """Report the number of unexpected trailing payload bytes."""
    reader = _SDCPPayloadReader(b"\x12\x34")

    with pytest.raises(ValueError, match="2 unexpected trailing bytes"):
        reader.ensure_end()


@pytest.mark.parametrize("payload", ["payload", bytearray(b"payload")])
def test_payload_reader_requires_bytes(payload: object) -> None:
    """Require the cursor reader input to be immutable bytes."""
    with pytest.raises(TypeError, match="Payload must be bytes"):
        _SDCPPayloadReader(payload)  # type: ignore[arg-type]


def test_deserialize_requires_bytes() -> None:
    """Require complete SDCP frames to be immutable bytes."""
    with pytest.raises(TypeError, match="Payload must be bytes"):
        SDCPSerializer.deserialize("01001234")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "frame, message",
    [
        ("040012345678", "requested 1 bytes.*only 0 remain"),
        ("04001234203100", "requested 1 bytes.*only 0 remain"),
        ("0400123420310001006407D000", "1 unexpected trailing bytes"),
        ("04001234203100010064", "requested 2 bytes.*only 0 remain"),
        ("0400123420310003006407D0", "unknown subscription mode: 0x03"),
    ],
)
def test_deserialize_subscription_requests_reject_invalid_payloads(
    frame: str, message: str
) -> None:
    """Reject trailing, truncated, and unknown-mode Subscribe payloads."""
    with pytest.raises(ValueError, match=message):
        SDCPSerializer.deserialize(bytes.fromhex(frame))


def test_identification_response_requires_revision_number() -> None:
    """Keep Identification responses strict at the documented 13-byte layout."""
    with pytest.raises(ValueError, match="requested 4 bytes.*only 0 remain"):
        SDCPSerializer.deserialize(bytes.fromhex("01011234001234567890ABCDEF"))


@pytest.mark.parametrize(
    "frame, expected_message",
    [
        ("01001234", SDCPIdentificationRequest(0x1234)),
        ("02001236100B00", SDCPReadRequest(0x1236, 0x100B, 0x00)),
        (
            "0300123428210042C80000",
            SDCPWriteRequest(0x1234, 0x2821, 0x00, bytes.fromhex("42C80000")),
        ),
        (
            "0400123420310001006407D0",
            SDCPPeriodicSubscriptionRequest(0x1234, 0x2031, 0x00, 100, 2000),
        ),
        ("040012342E4D000207D0", SDCPEventSubscriptionRequest(0x1234, 0x2E4D, 0x00, 2000)),
        ("050012345678", SDCPUnsubscribeRequest(0x1234, 0x5678)),
        (
            "01011234001234567890ABCDEF00000000",
            SDCPIdentificationResponse(0x1234, 0, 0x12345678, 0x90ABCDEF, 0),
        ),
        ("0201123412345678", SDCPReadResponse(0x1234, bytes.fromhex("12345678"))),
        ("03011234", SDCPWriteResponse(0x1234)),
        ("040112345678", SDCPSubscribeResponse(0x1234, 0x5678)),
        ("05011234", SDCPUnsubscribeResponse(0x1234)),
    ],
)
def test_deserialize_frame_matches_expected_message(frame: str, expected_message: object) -> None:
    """Deserialize every documented frame layout into its specialized message."""
    assert SDCPSerializer.deserialize(bytes.fromhex(frame)) == expected_message


@pytest.mark.parametrize(
    "frame, expected_message",
    [
        ("FF001234ABCD", SDCPUnknownFrame(0xFF, 0x00, 0x1234, bytes.fromhex("ABCD"))),
        ("02801234ABCD", SDCPUnknownFrame(0x02, 0x80, 0x1234, bytes.fromhex("ABCD"))),
    ],
)
def test_deserialize_unknown_frame(frame: str, expected_message: SDCPUnknownFrame) -> None:
    """Preserve unsupported opcodes and flags without guessing their layout."""
    decoded_message = SDCPSerializer.deserialize(bytes.fromhex(frame))

    assert decoded_message == expected_message


@pytest.mark.parametrize(
    "frame, expected_message",
    [
        (
            "01031234FFFF0001",
            SDCPIdentificationResponseError(0x1234, 0xFFFF0001),
        ),
        ("02031234FFFF0001", SDCPReadResponseError(0x1234, 0xFFFF0001)),
        (
            "03031234FFFF0001",
            SDCPWriteResponseError(0x1234, 0xFFFF0001),
        ),
        (
            "04031234FFFF0001",
            SDCPSubscribeResponseError(0x1234, 0xFFFF0001),
        ),
        (
            "05031234FFFF0001",
            SDCPUnsubscribeResponseError(0x1234, 0xFFFF0001),
        ),
    ],
)
def test_deserialize_specialized_error_responses(
    frame: str, expected_message: SDCPErrorResponse
) -> None:
    """Decode each known operation's error response into its specific type."""
    decoded_message = SDCPSerializer.deserialize(bytes.fromhex(frame))

    assert decoded_message == expected_message
    assert isinstance(decoded_message, SDCPErrorResponse)


def test_message_representation_uses_protocol_field_formats() -> None:
    """Fixed-width protocol fields use hexadecimal formatting."""
    write_request = SDCPWriteRequest(0x1234, 0x2821, 0x00, bytes.fromhex("42C80000"))
    periodic_subscription = SDCPPeriodicSubscriptionRequest(0x1234, 0x2031, 0x00, 100, 2000)
    identification_response = SDCPIdentificationResponse(0x1234, 0, 0x12345678, 0x90ABCDEF, 0)
    unsubscribe_request = SDCPUnsubscribeRequest(0x1234, 0x5678)
    error_response = SDCPReadResponseError(0x1234, 0xFFFF0001)

    assert repr(write_request) == (
        "SDCPWriteRequest(transaction_id=0x1234, index=0x2821, subindex=0x00, value=0x42C80000)"
    )
    assert repr(periodic_subscription) == (
        "SDCPPeriodicSubscriptionRequest(transaction_id=0x1234, index=0x2031, subindex=0x00, "
        "cyclic_time_ms=0x0064, message_count=0x07D0)"
    )
    assert repr(identification_response) == (
        "SDCPIdentificationResponse(transaction_id=0x1234, protocol_version=0x00, "
        "serial_number=0x12345678, product_code=0x90ABCDEF, revision_number=0x00000000)"
    )
    assert repr(unsubscribe_request) == (
        "SDCPUnsubscribeRequest(transaction_id=0x1234, subscription_id=0x5678)"
    )
    assert (
        repr(error_response)
        == "SDCPReadResponseError(transaction_id=0x1234, error_code=0xFFFF0001)"
    )


@pytest.mark.parametrize(
    "frame",
    [
        "",
        "01",
        "010012",
        "0100123400",  # Identification requests cannot contain trailing bytes.
        "02001234",  # Read request is missing its dictionary address.
        "0200123426E60000",  # Read request cannot contain trailing payload bytes.
        "03001234282100",  # Write requests require a non-empty value.
        "05001234",  # Unsubscribe requests require a subscription identifier.
        "0301123400",  # Write success responses cannot contain payload bytes.
        "04011234",  # Subscribe responses require a subscription identifier.
        "04011234567800",  # Subscribe responses cannot contain trailing payload bytes.
        "0501123400",  # Unsubscribe responses cannot contain payload bytes.
        # Identification responses cannot contain trailing bytes.
        "01011234001234567890ABCDEF0000000000",
        "02031234FFFF",  # Error responses require a 32-bit error code.
        "02031234FFFF0001FF",  # Error responses cannot contain trailing bytes.
    ],
)
def test_deserialize_rejects_malformed_known_frames(frame: str) -> None:
    """Reject known message types whose payload does not match the protocol layout."""
    with pytest.raises(ValueError):
        SDCPSerializer.deserialize(bytes.fromhex(frame))


@pytest.mark.parametrize(
    "serializer, arguments",
    [
        (SDCPSerializer.serialize_identification_request, (0x1_0000,)),
        (SDCPSerializer.serialize_read_request, (0x1234, 0x1_0000, 0x00)),
        (SDCPSerializer.serialize_read_request, (0x1234, 0x100B, 0x100)),
        (SDCPSerializer.serialize_unsubscribe_request, (0x1234, 0x1_0000)),
        (SDCPSerializer.serialize_error_response, (0x02, 0x1234, 0x1_0000_0000)),
        (SDCPSerializer.serialize_periodic_subscription_request, (-1, 0x2031, 0x00, 100, 2000)),
    ],
)
def test_serialize_rejects_out_of_range_fields(
    serializer: Callable[..., bytes], arguments: tuple[int, ...]
) -> None:
    """Reject public-builder fields that cannot fit their protocol positions."""
    with pytest.raises(ValueError):
        serializer(*arguments)


@pytest.mark.parametrize(
    "serializer, arguments",
    [
        (SDCPSerializer.serialize_identification_request, (True,)),
        (SDCPSerializer.serialize_read_request, (0x1234, "0x100B", 0x00)),
        (SDCPSerializer.serialize_unsubscribe_request, (0x1234, False)),
        (SDCPSerializer.serialize_error_response, (0x02, 0x1234, 1.0)),
    ],
)
def test_serialize_rejects_invalid_uint_types(
    serializer: Callable[..., bytes], arguments: tuple[object, ...]
) -> None:
    """Reject non-integer and boolean values for unsigned protocol fields."""
    with pytest.raises(TypeError):
        serializer(*arguments)


@pytest.mark.parametrize(
    "value, expected_exception",
    [(b"", ValueError), ("value", TypeError), (bytearray(b"value"), TypeError)],
)
def test_serialize_rejects_invalid_write_values(
    value: object, expected_exception: type[BaseException]
) -> None:
    """Require a non-empty bytes value payload for a Write request."""
    with pytest.raises(expected_exception):
        SDCPSerializer.serialize_write_request(0x1234, 0x2821, 0x00, value)  # type: ignore[arg-type]


@pytest.mark.parametrize("payload", ["payload", bytearray(b"payload")])
def test_serialize_rejects_invalid_response_payload_types(payload: object) -> None:
    """Require raw response payloads to be immutable bytes."""
    with pytest.raises(TypeError):
        SDCPSerializer.serialize_success_response(0x02, 0x1234, payload)  # type: ignore[arg-type]
