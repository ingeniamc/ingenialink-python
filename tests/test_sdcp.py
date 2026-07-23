"""Tests for SDCP acyclic frame serialization."""

from __future__ import annotations

import pytest

from ingenialink.utils.sdcp import SDCPFlag, SDCPFrame, SDCPOpcode, SDCPSerializer


def test_serialize_read_request() -> None:
    """Serialize the read request from the SDCP protocol specification."""
    frame = SDCPSerializer.serialize(
        SDCPOpcode.READ,
        SDCPFlag.NONE,
        0x1234,
        0x26E6,
        0x00,
    )

    # The transaction ID is encoded as the big-endian bytes 12 34.
    assert frame == bytes.fromhex("0200123426E600")


def test_serialize_write_request() -> None:
    """Serialize the Write request from the SDCP protocol specification."""
    frame = SDCPSerializer.serialize(
        SDCPOpcode.WRITE,
        SDCPFlag.NONE,
        0x1234,
        0x2821,
        0x00,
        bytes.fromhex("42C80000"),
    )

    # The value bytes follow the index and subindex fields.
    assert frame == bytes.fromhex("0300123428210042C80000")


def test_deserialize_read_response() -> None:
    """Deserialize the successful read response from the specification."""
    decoded_frame = SDCPSerializer.deserialize(bytes.fromhex("0201123412345678"))

    assert decoded_frame.opcode == SDCPOpcode.READ
    assert decoded_frame.flags == SDCPFlag.REPLY
    assert decoded_frame.transaction_id == 0x1234
    assert decoded_frame.payload == bytes.fromhex("12345678")
    assert decoded_frame.index is None
    assert decoded_frame.subindex is None


@pytest.mark.parametrize(
    "frame, expected_frame",
    [
        # Read requests contain only the dictionary address after the header.
        (
            "02001236100B00",
            SDCPFrame(SDCPOpcode.READ, SDCPFlag.NONE, 0x1236, b"", 0x100B, 0x00),
        ),
        # Write requests retain only the value after their dictionary address.
        (
            "0300123428210042C80000",
            SDCPFrame(
                SDCPOpcode.WRITE, SDCPFlag.NONE, 0x1234, bytes.fromhex("42C80000"), 0x2821, 0x00
            ),
        ),
        # Error replies do not contain a dictionary address.
        (
            "02031236FFFF0001",
            SDCPFrame(
                SDCPOpcode.READ, SDCPFlag.REPLY | SDCPFlag.ERROR, 0x1236, bytes.fromhex("FFFF0001")
            ),
        ),
    ],
)
def test_deserialize_frame_matches_expected_frame(frame: str, expected_frame: SDCPFrame) -> None:
    """Deserialize a protocol frame into its complete expected frame object."""
    assert SDCPSerializer.deserialize(bytes.fromhex(frame)) == expected_frame


def test_round_trip_error_response() -> None:
    """Keep an error reply payload unchanged through a serialize round trip."""
    received_frame = bytes.fromhex("0203123406020000")
    decoded_frame = SDCPSerializer.deserialize(received_frame)

    # Error details are opcode-specific, so the serializer preserves raw payload bytes.
    serialized_frame = SDCPSerializer.serialize(
        decoded_frame.opcode,
        decoded_frame.flags,
        decoded_frame.transaction_id,
        payload=decoded_frame.payload,
    )

    assert serialized_frame == received_frame


def test_frame_representation_uses_protocol_names() -> None:
    """Display the opcode, flags, and transaction ID in protocol-friendly form."""
    decoded_frame = SDCPSerializer.deserialize(bytes.fromhex("02031236FFFF0001"))

    # An error reply includes both the reply and error flag bits.
    assert repr(decoded_frame) == (
        "SDCPFrame(opcode=READ, flags=REPLY | ERROR, transaction_id=0x1236, payload=0xFFFF0001)"
    )


def test_frame_representation_uses_none_for_a_request_without_flags() -> None:
    """Display an unflagged read request with its dictionary address fields."""
    decoded_frame = SDCPSerializer.deserialize(bytes.fromhex("02001236100B00"))

    assert decoded_frame.index == 0x100B
    assert decoded_frame.subindex == 0x00
    assert decoded_frame.payload == b""
    assert (
        repr(decoded_frame) == "SDCPFrame(opcode=READ, flags=NONE, transaction_id=0x1236, "
        "index=0x100B, subindex=0x00, payload=0x)"
    )


@pytest.mark.parametrize(
    "frame, expected_index, expected_subindex, expected_payload",
    [
        # Write requests append the value after the index and subindex.
        ("0300123428210042C80000", 0x2821, 0x00, bytes.fromhex("42C80000")),
        # Subscribe requests append mode, period, and message count.
        ("0400123420310001006407D0", 0x2031, 0x00, bytes.fromhex("01006407D0")),
    ],
)
def test_deserialize_dictionary_request_address(
    frame: str, expected_index: int, expected_subindex: int, expected_payload: bytes
) -> None:
    """Parse the address before the operation-specific request parameters."""
    decoded_frame = SDCPSerializer.deserialize(bytes.fromhex(frame))

    assert decoded_frame.index == expected_index
    assert decoded_frame.subindex == expected_subindex
    assert decoded_frame.payload == expected_payload


@pytest.mark.parametrize(
    "opcode, flags, transaction_id",
    [
        (0x100, 0, 0),
        (0, 0x100, 0),
        (0, 0, 0x1_0000),
    ],
)
def test_serialize_rejects_oversized_header_fields(
    opcode: int, flags: int, transaction_id: int
) -> None:
    """Reject fields that cannot fit in their SDCP header positions."""
    with pytest.raises(ValueError):
        SDCPSerializer.serialize(opcode, flags, transaction_id)


@pytest.mark.parametrize(
    "index, subindex",
    [
        (0x100B, None),
        (None, 0x00),
        (0x1_0000, 0x00),
        (0x100B, 0x100),
    ],
)
def test_serialize_rejects_invalid_dictionary_address(
    index: int | None, subindex: int | None
) -> None:
    """Require a complete dictionary address that fits the protocol fields."""
    with pytest.raises(ValueError):
        SDCPSerializer.serialize(
            SDCPOpcode.READ, SDCPFlag.NONE, 0x1234, index=index, subindex=subindex
        )


def test_serialize_rejects_dictionary_request_without_address() -> None:
    """Require an index and subindex for a dictionary request."""
    with pytest.raises(ValueError, match="require index and subindex"):
        SDCPSerializer.serialize(SDCPOpcode.READ, SDCPFlag.NONE, 0x1234)


def test_serialize_rejects_write_request_without_value() -> None:
    """Require a value payload for a Write request after its dictionary address."""
    with pytest.raises(ValueError, match="require a value payload"):
        SDCPSerializer.serialize(SDCPOpcode.WRITE, SDCPFlag.NONE, 0x1234, 0x2821, 0x00)


@pytest.mark.parametrize("frame", [b"", b"\x01", b"\x01\x00\x12"])
def test_deserialize_rejects_incomplete_header(frame: bytes) -> None:
    """Reject a datagram that does not contain the full SDCP header."""
    with pytest.raises(ValueError, match="four-byte header"):
        SDCPSerializer.deserialize(frame)
