"""Tests for SDCP message serialization and deserialization."""

from __future__ import annotations

import pytest

from ingenialink.utils.sdcp import (
    SDCPErrorResponse,
    SDCPEventSubscriptionRequest,
    SDCPIdentifyRequest,
    SDCPIdentifyResponse,
    SDCPPeriodicSubscriptionRequest,
    SDCPReadRequest,
    SDCPReadResponse,
    SDCPSerializer,
    SDCPSubscribeResponse,
    SDCPUnknownFrame,
    SDCPUnsubscribeRequest,
    SDCPUnsubscribeResponse,
    SDCPWriteRequest,
    SDCPWriteResponse,
)


def test_serialize_identify_request() -> None:
    """Serialize the Identify request from the SDCP protocol specification."""
    assert SDCPSerializer.serialize_identify_request(0x1234) == bytes.fromhex("01001234")


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


@pytest.mark.parametrize(
    "frame, expected_message",
    [
        ("01001234", SDCPIdentifyRequest(0x1234)),
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
            SDCPIdentifyResponse(0x1234, bytes.fromhex("001234567890ABCDEF00000000")),
        ),
        ("0201123412345678", SDCPReadResponse(0x1234, bytes.fromhex("12345678"))),
        ("03011234", SDCPWriteResponse(0x1234)),
        ("040112345678", SDCPSubscribeResponse(0x1234, 0x5678)),
        ("05011234", SDCPUnsubscribeResponse(0x1234)),
        ("02031236FFFF0001", SDCPErrorResponse(0x02, 0x1236, 0xFFFF0001)),
    ],
)
def test_deserialize_frame_matches_expected_message(frame: str, expected_message: object) -> None:
    """Deserialize every documented frame layout into its specialized message."""
    assert SDCPSerializer.deserialize(bytes.fromhex(frame)) == expected_message


def test_deserialize_unknown_frame() -> None:
    """Preserve unrecognized opcode and flag combinations without guessing their layout."""
    decoded_message = SDCPSerializer.deserialize(bytes.fromhex("FF801234ABCD"))

    assert decoded_message == SDCPUnknownFrame(0xFF, 0x80, 0x1234, bytes.fromhex("ABCD"))


def test_message_representation_uses_hexadecimal_values() -> None:
    """Display every protocol value in hexadecimal instead of decimal."""
    write_request = SDCPWriteRequest(0x1234, 0x2821, 0x00, bytes.fromhex("42C80000"))
    periodic_subscription = SDCPPeriodicSubscriptionRequest(0x1234, 0x2031, 0x00, 100, 2000)

    assert repr(write_request) == (
        "SDCPWriteRequest(transaction_id=0x1234, index=0x2821, subindex=0x00, value=0x42C80000)"
    )
    assert repr(periodic_subscription) == (
        "SDCPPeriodicSubscriptionRequest(transaction_id=0x1234, index=0x2031, subindex=0x00, "
        "cyclic_time_ms=0x0064, message_count=0x07D0)"
    )


@pytest.mark.parametrize(
    "frame",
    [
        "",
        "01",
        "010012",
        "02001234",  # Read request is missing its dictionary address.
        "0301123400",  # Write success responses cannot contain payload bytes.
        "02031234FFFF",  # Error responses require a 32-bit error code.
        "04001234203100010064",  # Periodic subscription is missing its message count.
    ],
)
def test_deserialize_rejects_malformed_known_frames(frame: str) -> None:
    """Reject known message types whose payload does not match the protocol layout."""
    with pytest.raises(ValueError):
        SDCPSerializer.deserialize(bytes.fromhex(frame))


@pytest.mark.parametrize(
    "serializer, arguments",
    [
        (SDCPSerializer.serialize_identify_request, (0x1_0000,)),
        (SDCPSerializer.serialize_read_request, (0x1234, 0x1_0000, 0x00)),
        (SDCPSerializer.serialize_read_request, (0x1234, 0x100B, 0x100)),
        (SDCPSerializer.serialize_unsubscribe_request, (0x1234, 0x1_0000)),
    ],
)
def test_serialize_rejects_out_of_range_fields(
    serializer: object, arguments: tuple[int, ...]
) -> None:
    """Reject public-builder fields that cannot fit their protocol positions."""
    with pytest.raises(ValueError):
        serializer(*arguments)  # type: ignore[operator]


def test_serialize_rejects_empty_write_value() -> None:
    """Require a value payload for a Write request."""
    with pytest.raises(ValueError, match="require a value payload"):
        SDCPSerializer.serialize_write_request(0x1234, 0x2821, 0x00, b"")
