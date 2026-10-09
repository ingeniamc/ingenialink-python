"""Tests for SDCP message serialization and deserialization."""

from __future__ import annotations

import pytest

from ingenialink.ethernet.tsn.sdcp.enums import (
    SDCPDeviceMode,
    SDCPFlag,
    SDCPOpcode,
    SDCPProfileFlags,
)
from ingenialink.ethernet.tsn.sdcp.messages import (
    SDCPDeserializer,
    SDCPErrorResponse,
    SDCPIdentificationRequest,
    SDCPIdentificationResponse,
    SDCPIdentificationResponseError,
    SDCPReadRequest,
    SDCPReadResponse,
    SDCPReadResponseError,
    SDCPUnknownFrame,
    SDCPWriteRequest,
    SDCPWriteResponse,
    SDCPWriteResponseError,
    _SDCPField,
    _SDCPFields,
    _SDCPMessage,
    _SDCPPayloadReader,
)


@pytest.mark.parametrize(
    "message, expected_frame",
    [
        (
            SDCPIdentificationRequest(0x1234),
            bytes.fromhex("01001234"),
        ),
        (
            SDCPReadRequest(0x1234, 0x26E6, 0x00),
            bytes.fromhex("0200123426E600"),
        ),
        (
            SDCPWriteRequest(0x1234, 0x2821, 0x00, bytes.fromhex("42C80000")),
            bytes.fromhex("0300123428210042C80000"),
        ),
        (
            SDCPIdentificationResponse(
                0x1234,
                0,
                SDCPProfileFlags.SECURITY | SDCPProfileFlags.SAFETY,
                SDCPDeviceMode.BOOTLOADER,
                0x12345678,
                0x90ABCDEF,
                0,
            ),
            bytes.fromhex("01011234000005011234567890ABCDEF00000000"),
        ),
        (
            SDCPReadResponse(0x1234, bytes.fromhex("12345678")),
            bytes.fromhex("0201123412345678"),
        ),
        (
            SDCPWriteResponse(0x1234),
            bytes.fromhex("03011234"),
        ),
        (
            SDCPIdentificationResponseError(0x1234, 0x0001),
            bytes.fromhex("010312340001"),
        ),
        (
            SDCPReadResponseError(0x1234, 0x0001),
            bytes.fromhex("020312340001"),
        ),
        (
            SDCPWriteResponseError(0x1234, 0x0001),
            bytes.fromhex("030312340001"),
        ),
        (
            SDCPUnknownFrame(0x1234, 0xFF, 0x80, bytes.fromhex("ABCD")),
            bytes.fromhex("FF801234ABCD"),
        ),
    ],
)
def test_serialize_message_objects(message: _SDCPMessage, expected_frame: bytes) -> None:
    """Serialize every supported typed message into its specification frame."""
    assert bytes(message) == expected_frame


@pytest.mark.parametrize(
    "message",
    [
        SDCPIdentificationRequest(0x1234),
        SDCPReadRequest(0x1234, 0x26E6, 0x00),
        SDCPWriteRequest(0x1234, 0x2821, 0x00, bytes.fromhex("42C80000")),
        SDCPIdentificationResponse(
            0x1234,
            0,
            SDCPProfileFlags.SECURITY | SDCPProfileFlags.SAFETY,
            SDCPDeviceMode.BOOTLOADER,
            0x12345678,
            0x90ABCDEF,
            0,
        ),
        SDCPReadResponse(0x1234, bytes.fromhex("12345678")),
        SDCPWriteResponse(0x1234),
        SDCPIdentificationResponseError(0x1234, 0x0001),
        SDCPReadResponseError(0x1234, 0x0001),
        SDCPWriteResponseError(0x1234, 0x0001),
        SDCPUnknownFrame(0x1234, 0xFF, 0x80, bytes.fromhex("ABCD")),
    ],
)
def test_deserialize_serialized_message(message: _SDCPMessage) -> None:
    """Round-trip every concrete message through SDCP frame deserialization."""
    assert SDCPDeserializer.deserialize(bytes(message)) == message


@pytest.mark.parametrize(
    "message, expected_opcode",
    [
        (SDCPIdentificationResponseError(0x1234, 0x0001), SDCPOpcode.IDENTIFICATION),
        (SDCPReadResponseError(0x1234, 0x0001), SDCPOpcode.READ),
        (SDCPWriteResponseError(0x1234, 0x0001), SDCPOpcode.WRITE),
    ],
)
def test_serialize_error_response_uses_opcode_and_error_flags(
    message: SDCPErrorResponse, expected_opcode: SDCPOpcode
) -> None:
    """Encode each concrete error response with its operation opcode and flags."""
    frame = bytes(message)

    assert frame[:2] == bytes((expected_opcode, SDCPFlag.REPLY | SDCPFlag.ERROR))
    assert SDCPDeserializer.deserialize(frame) == message


@pytest.mark.parametrize("error_code", [0x0000, 0xFFFF])
def test_error_response_round_trips_uint16_boundary_codes(error_code: int) -> None:
    """Preserve both boundary values of the 16-bit error-code field."""
    response = SDCPReadResponseError(0x1234, error_code)

    frame = bytes(response)

    assert len(frame) == 6
    assert frame[-2:] == error_code.to_bytes(2, "big")
    assert SDCPDeserializer.deserialize(frame) == response


def test_serialize_rejects_base_error_response() -> None:
    """Keep the base error response abstract and non-serializable."""
    with pytest.raises(TypeError, match="abstract method"):
        SDCPErrorResponse(0x1234, 0x0001)


def test_message_base_is_abstract() -> None:
    """Require concrete message types to implement the byte interface."""
    with pytest.raises(TypeError, match="abstract method"):
        _SDCPMessage(0x1234)


def test_sdcp_field_serializes_fixed_width_big_endian_values() -> None:
    """Serialize unsigned values using the field width and protocol byte order."""
    field = _SDCPField(2)

    assert field.size == 2
    assert field.hex_width == 4
    assert field.maximum_value == 0xFFFF
    assert field.serialize(0x1234) == bytes.fromhex("1234")
    assert field.serialize(field.maximum_value) == bytes.fromhex("FFFF")


@pytest.mark.parametrize("value", [True, False, "0x1234", 1.0])
def test_sdcp_field_rejects_non_integer_values(value: object) -> None:
    """Reject booleans and other non-integer values before encoding."""
    with pytest.raises(TypeError, match="Value must be an integer for a 2-byte field"):
        _SDCPField(2).serialize(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [-1, 0x1_0000])
def test_sdcp_field_rejects_values_outside_unsigned_range(value: int) -> None:
    """Reject values outside the field's unsigned range."""
    with pytest.raises(ValueError, match="Value must be in the range 0 to 65535"):
        _SDCPField(2).serialize(value)


@pytest.mark.parametrize(
    "message, expected_message",
    [
        (SDCPReadResponse(0x1234, "value"), "value must be bytes"),
        (SDCPUnknownFrame(0x1234, 0xFF, 0x00, bytearray(b"payload")), "payload must be bytes"),
    ],
)
def test_serialize_rejects_invalid_raw_response_payloads(
    message: _SDCPMessage, expected_message: str
) -> None:
    """Require immutable bytes for raw payloads on typed response objects."""
    with pytest.raises(TypeError, match=expected_message):
        bytes(message)


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
        SDCPDeserializer.deserialize("01001234")  # type: ignore[arg-type]


def test_identification_response_requires_revision_number() -> None:
    """Keep Identification responses strict at the documented 16-byte layout."""
    with pytest.raises(ValueError, match="requested 4 bytes.*only 0 remain"):
        SDCPDeserializer.deserialize(bytes.fromhex("01011234000000001234567890ABCDEF"))


@pytest.mark.parametrize(
    "profile_flags, device_mode",
    [
        (SDCPProfileFlags(0), SDCPDeviceMode.APPLICATION),
        (SDCPProfileFlags.SECURITY, SDCPDeviceMode.APPLICATION),
        (SDCPProfileFlags.REALTIME, SDCPDeviceMode.APPLICATION),
        (SDCPProfileFlags.SAFETY, SDCPDeviceMode.APPLICATION),
        (
            SDCPProfileFlags.SECURITY | SDCPProfileFlags.REALTIME | SDCPProfileFlags.SAFETY,
            SDCPDeviceMode.BOOTLOADER,
        ),
    ],
)
def test_identification_response_round_trips_profile_flags_and_device_mode(
    profile_flags: SDCPProfileFlags, device_mode: SDCPDeviceMode
) -> None:
    """Round-trip empty, individual, and combined profiles across valid device modes."""
    response = SDCPIdentificationResponse(
        transaction_id=0x1234,
        protocol_version=1,
        profile_flags=profile_flags,
        device_mode=device_mode,
        serial_number=0x12345678,
        product_code=0x90ABCDEF,
        revision_number=0x00010002,
    )

    frame = bytes(response)

    assert len(frame) == 20
    assert frame[5:8] == int(profile_flags).to_bytes(2, "big") + int(device_mode).to_bytes(1, "big")
    assert SDCPDeserializer.deserialize(frame) == response


def test_identification_response_normalizes_directly_constructed_enum_fields() -> None:
    """Normalize valid integer protocol values when constructing a response."""
    response = SDCPIdentificationResponse(
        transaction_id=0x1234,
        protocol_version=1,
        profile_flags=SDCPProfileFlags.SECURITY.value,
        device_mode=SDCPDeviceMode.BOOTLOADER.value,
        serial_number=0x12345678,
        product_code=0x90ABCDEF,
        revision_number=0x00010002,
    )

    assert response.profile_flags is SDCPProfileFlags.SECURITY
    assert response.device_mode is SDCPDeviceMode.BOOTLOADER


@pytest.mark.parametrize(
    "profile_flags, device_mode, message",
    [
        (0x0008, 0x00, "reserved profile flag bits set"),
        (0x0000, 0x02, "unknown device mode: 0x02"),
    ],
)
def test_identification_response_rejects_reserved_values_on_direct_construction(
    profile_flags: int, device_mode: int, message: str
) -> None:
    """Reject reserved protocol values when constructing a response directly."""
    with pytest.raises(ValueError, match=message):
        SDCPIdentificationResponse(
            transaction_id=0x1234,
            protocol_version=1,
            profile_flags=profile_flags,
            device_mode=device_mode,
            serial_number=0x12345678,
            product_code=0x90ABCDEF,
            revision_number=0x00010002,
        )


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
            "01011234000005011234567890ABCDEF00000000",
            SDCPIdentificationResponse(
                0x1234,
                0,
                SDCPProfileFlags.SECURITY | SDCPProfileFlags.SAFETY,
                SDCPDeviceMode.BOOTLOADER,
                0x12345678,
                0x90ABCDEF,
                0,
            ),
        ),
        ("0201123412345678", SDCPReadResponse(0x1234, bytes.fromhex("12345678"))),
        ("03011234", SDCPWriteResponse(0x1234)),
    ],
)
def test_deserialize_frame_matches_expected_message(frame: str, expected_message: object) -> None:
    """Deserialize every documented frame layout into its specialized message."""
    assert SDCPDeserializer.deserialize(bytes.fromhex(frame)) == expected_message


@pytest.mark.parametrize(
    "frame, expected_message",
    [
        ("FF001234ABCD", SDCPUnknownFrame(0x1234, 0xFF, 0x00, bytes.fromhex("ABCD"))),
        ("02801234ABCD", SDCPUnknownFrame(0x1234, 0x02, 0x80, bytes.fromhex("ABCD"))),
        ("04001234ABCD", SDCPUnknownFrame(0x1234, 0x04, SDCPFlag.NONE, bytes.fromhex("ABCD"))),
        ("05011234ABCD", SDCPUnknownFrame(0x1234, 0x05, SDCPFlag.REPLY, bytes.fromhex("ABCD"))),
        (
            "040312340001",
            SDCPUnknownFrame(
                0x1234,
                0x04,
                SDCPFlag.REPLY | SDCPFlag.ERROR,
                bytes.fromhex("0001"),
            ),
        ),
    ],
)
def test_deserialize_unknown_frame(frame: str, expected_message: SDCPUnknownFrame) -> None:
    """Preserve unsupported opcodes and flags without guessing their layout."""
    decoded_message = SDCPDeserializer.deserialize(bytes.fromhex(frame))

    assert decoded_message == expected_message
    assert bytes(decoded_message) == bytes.fromhex(frame)


@pytest.mark.parametrize("opcode", [0x04, 0x05])
def test_reserved_core_opcodes_are_not_defined(opcode: int) -> None:
    """Keep reserved Subscribe and Unsubscribe opcodes out of the Core enum."""
    with pytest.raises(ValueError):
        SDCPOpcode(opcode)


@pytest.mark.parametrize(
    "frame, expected_message",
    [
        (
            "010312340001",
            SDCPIdentificationResponseError(0x1234, 0x0001),
        ),
        ("020312340001", SDCPReadResponseError(0x1234, 0x0001)),
        (
            "030312340001",
            SDCPWriteResponseError(0x1234, 0x0001),
        ),
    ],
)
def test_deserialize_specialized_error_responses(
    frame: str, expected_message: SDCPErrorResponse
) -> None:
    """Decode each known operation's error response into its specific type."""
    decoded_message = SDCPDeserializer.deserialize(bytes.fromhex(frame))

    assert decoded_message == expected_message
    assert isinstance(decoded_message, SDCPErrorResponse)


def test_message_representation_uses_protocol_field_formats() -> None:
    """Fixed-width protocol fields use hexadecimal formatting."""
    write_request = SDCPWriteRequest(0x1234, 0x2821, 0x00, bytes.fromhex("42C80000"))
    identification_response = SDCPIdentificationResponse(
        0x1234,
        0,
        SDCPProfileFlags.SECURITY | SDCPProfileFlags.SAFETY,
        SDCPDeviceMode.BOOTLOADER,
        0x12345678,
        0x90ABCDEF,
        0,
    )
    error_response = SDCPReadResponseError(0x1234, 0x0001)

    assert repr(write_request) == (
        "SDCPWriteRequest(transaction_id=0x1234, index=0x2821, subindex=0x00, value=0x42C80000)"
    )
    assert repr(identification_response) == (
        "SDCPIdentificationResponse(transaction_id=0x1234, protocol_version=0x00, "
        "profile_flags=0x0005, device_mode=0x01, serial_number=0x12345678, "
        "product_code=0x90ABCDEF, revision_number=0x00000000)"
    )
    assert repr(error_response) == "SDCPReadResponseError(transaction_id=0x1234, error_code=0x0001)"


@pytest.mark.parametrize(
    "frame, message",
    [
        pytest.param("", "four-byte header", id="truncated-header"),
        pytest.param("01", "four-byte header", id="truncated-header-opcode"),
        pytest.param("010012", "four-byte header", id="truncated-header-transaction-id"),
        pytest.param(
            "0100123400", "1 unexpected trailing bytes", id="identification-request-trailing"
        ),
        pytest.param(
            "01011234000005011234567890ABCDEF0000000000",
            "1 unexpected trailing bytes",
            id="identification-response-trailing",
        ),
        pytest.param(
            "01011234000008001234567890ABCDEF00000000",
            "reserved profile flag bits set",
            id="identification-response-reserved-profile-flags",
        ),
        pytest.param(
            "01011234000000021234567890ABCDEF00000000",
            "unknown device mode: 0x02",
            id="identification-response-reserved-device-mode",
        ),
        pytest.param(
            "02001234", "requested 2 bytes.*only 0 remain", id="read-request-truncated-address"
        ),
        pytest.param("0200123426E60000", "1 unexpected trailing bytes", id="read-request-trailing"),
        pytest.param(
            "03001234282100", "Write requests require a value payload", id="write-request-empty"
        ),
        pytest.param("0301123400", "1 unexpected trailing bytes", id="write-response-trailing"),
        pytest.param(
            "0203123400",
            "requested 2 bytes.*only 1 remain",
            id="error-response-truncated-code",
        ),
        pytest.param(
            "020312340001FF",
            "1 unexpected trailing bytes",
            id="error-response-trailing",
        ),
    ],
)
def test_deserialize_rejects_malformed_frames(frame: str, message: str) -> None:
    """Reject malformed SDCP headers and message payloads for their expected reasons."""
    with pytest.raises(ValueError, match=message):
        SDCPDeserializer.deserialize(bytes.fromhex(frame))


@pytest.mark.parametrize(
    "message",
    [
        SDCPIdentificationRequest(0x1_0000),
        SDCPReadRequest(0x1234, 0x1_0000, 0x00),
        SDCPReadRequest(0x1234, 0x100B, 0x100),
        SDCPReadResponseError(0x1234, 0x1_0000),
    ],
)
def test_serialize_rejects_out_of_range_fields(message: _SDCPMessage) -> None:
    """Reject message fields that cannot fit their protocol positions."""
    with pytest.raises(ValueError):
        bytes(message)


@pytest.mark.parametrize(
    "message",
    [
        SDCPIdentificationRequest(True),
        SDCPReadRequest(0x1234, "0x100B", 0x00),
        SDCPReadResponseError(0x1234, True),
        SDCPReadResponseError(0x1234, 1.0),
    ],
)
def test_serialize_rejects_invalid_uint_types(message: _SDCPMessage) -> None:
    """Reject non-integer and boolean values for unsigned protocol fields."""
    with pytest.raises(TypeError):
        bytes(message)


@pytest.mark.parametrize(
    "value, expected_exception",
    [(b"", ValueError), ("value", TypeError), (bytearray(b"value"), TypeError)],
)
def test_serialize_rejects_invalid_write_values(
    value: object, expected_exception: type[BaseException]
) -> None:
    """Require a non-empty bytes value payload for a Write request."""
    with pytest.raises(expected_exception):
        bytes(SDCPWriteRequest(0x1234, 0x2821, 0x00, value))  # type: ignore[arg-type]
