"""SDCP message encoding and frame deserialization utilities."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, fields
from enum import IntEnum, IntFlag
from typing import Literal, Union


class SDCPOpcode(IntEnum):
    """Opcodes defined by the SDCP Core acyclic protocol."""

    IDENTIFICATION = 0x01
    READ = 0x02
    WRITE = 0x03


class SDCPFlag(IntFlag):
    """Flags defined by the SDCP acyclic communication protocol."""

    NONE = 0x00
    REPLY = 0x01
    ERROR = 0x02


class SDCPDeviceMode(IntEnum):
    """Device modes defined by the SDCP Identification response."""

    APPLICATION = 0x00
    BOOTLOADER = 0x01


class SDCPProfileFlags(IntFlag):
    """Profile flags defined by the SDCP Identification response."""

    SECURITY = 0x0001
    REALTIME = 0x0002
    SAFETY = 0x0004


_SDCP_BYTE_ORDER: Literal["big"] = "big"
_SDCP_PROFILE_FLAGS_RESERVED_MASK = 0xFFF8


@dataclass(frozen=True)
class _SDCPField:
    """Define and serialize a fixed-width SDCP field."""

    size: int

    def serialize(self, value: int) -> bytes:
        """Serialize an unsigned value using the protocol byte order.

        Returns:
            The fixed-width big-endian representation of the field.

        Raises:
            TypeError: If the value is not an integer or is a boolean.
            ValueError: If the value cannot fit in the field.

        """
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"Value must be an integer for a {self.size}-byte field")
        if not 0 <= value <= self.maximum_value:
            raise ValueError(f"Value must be in the range 0 to {self.maximum_value}")
        return value.to_bytes(self.size, _SDCP_BYTE_ORDER)

    @property
    def hex_width(self) -> int:
        """The field's hexadecimal display width."""
        return self.size * 2

    @property
    def maximum_value(self) -> int:
        """The largest unsigned value that fits in the field."""
        return (1 << (self.size * 8)) - 1


class _SDCPFields:
    """Fixed-width SDCP field definitions."""

    OPCODE = _SDCPField(1)
    FLAGS = _SDCPField(1)
    TRANSACTION_ID = _SDCPField(2)
    INDEX = _SDCPField(2)
    SUBINDEX = _SDCPField(1)
    ERROR_CODE = _SDCPField(2)
    PROTOCOL_VERSION = _SDCPField(1)
    PROFILE_FLAGS = _SDCPField(2)
    DEVICE_MODE = _SDCPField(1)
    SERIAL_NUMBER = _SDCPField(4)
    PRODUCT_CODE = _SDCPField(4)
    REVISION_NUMBER = _SDCPField(4)


class _SDCPPayloadReader:
    """Read sequential values from an SDCP payload."""

    def __init__(self, payload: bytes) -> None:
        if not isinstance(payload, bytes):
            raise TypeError("Payload must be bytes")
        self._payload = payload
        self._offset = 0

    def read_uint(self, field: _SDCPField) -> int:
        """Read a fixed-width unsigned integer.

        Returns:
            The decoded big-endian unsigned integer.

        """
        return int.from_bytes(self.read_bytes(field.size), _SDCP_BYTE_ORDER)

    def read_bytes(self, size: int) -> bytes:
        """Read a fixed number of bytes from the current offset.

        Returns:
            The requested payload bytes.

        Raises:
            ValueError: If the payload does not contain enough bytes.

        """
        if size < 0:
            raise ValueError("Payload read size cannot be negative")
        end = self._offset + size
        if end > len(self._payload):
            remaining = len(self._payload) - self._offset
            raise ValueError(f"Payload read requested {size} bytes, but only {remaining} remain")
        value = self._payload[self._offset : end]
        self._offset = end
        return value

    def read_remaining(self) -> bytes:
        """Read all bytes remaining in the payload.

        Returns:
            The unread payload bytes.

        """
        return self.read_bytes(len(self._payload) - self._offset)

    def ensure_end(self) -> None:
        """Ensure that the payload has been consumed completely.

        Raises:
            ValueError: If the payload contains unread bytes.

        """
        if self._offset != len(self._payload):
            trailing_bytes = len(self._payload) - self._offset
            raise ValueError(f"Payload contains {trailing_bytes} unexpected trailing bytes")


class _SDCPCodec:
    """Private SDCP encoding operations shared by message objects."""

    @staticmethod
    def serialize_frame(
        opcode: int,
        flags: int,
        transaction_id: int,
        payload: bytes = b"",
    ) -> bytes:
        """Serialize the common SDCP header and raw operation payload.

        Returns:
            The big-endian SDCP frame.

        Raises:
            TypeError: If the payload is not bytes.
            ValueError: If a header field does not fit its protocol-defined size.

        """
        if not isinstance(payload, bytes):
            raise TypeError("payload must be bytes")
        header = (
            _SDCPFields.OPCODE.serialize(opcode)
            + _SDCPFields.FLAGS.serialize(flags)
            + _SDCPFields.TRANSACTION_ID.serialize(transaction_id)
        )
        return header + payload


@dataclass(frozen=True, repr=False)
class _SDCPMessage(ABC):
    """Base class for typed SDCP messages."""

    transaction_id: int

    @abstractmethod
    def __bytes__(self) -> bytes:
        """Serialize this message into an SDCP frame."""
        raise NotImplementedError

    def __repr__(self) -> str:
        """Return a protocol-oriented representation.

        Returns:
            The message type and its fields formatted for debugging.

        """
        formatted_fields = []
        for message_field in fields(self):
            value = getattr(self, message_field.name)
            if isinstance(value, bytes):
                formatted_value = f"0x{value.hex().upper()}"
            elif isinstance(value, int):
                protocol_field = getattr(_SDCPFields, message_field.name.upper(), None)
                width = protocol_field.hex_width if protocol_field else 0
                formatted_value = f"0x{value:0{width}X}" if width else f"0x{value:X}"
            else:
                formatted_value = repr(value)
            formatted_fields.append(f"{message_field.name}={formatted_value}")

        return f"{type(self).__name__}({', '.join(formatted_fields)})"


@dataclass(frozen=True, repr=False)
class SDCPIdentificationRequest(_SDCPMessage):
    """An SDCP Identification request."""

    def __bytes__(self) -> bytes:
        """Serialize this Identification request.

        Returns:
            The binary SDCP frame.

        """
        return _SDCPCodec.serialize_frame(
            SDCPOpcode.IDENTIFICATION, SDCPFlag.NONE, self.transaction_id
        )


@dataclass(frozen=True, repr=False)
class SDCPReadRequest(_SDCPMessage):
    """An SDCP Read request."""

    index: int
    subindex: int

    def __bytes__(self) -> bytes:
        """Serialize this Read request.

        Returns:
            The binary SDCP frame.

        """
        payload = _SDCPFields.INDEX.serialize(self.index) + _SDCPFields.SUBINDEX.serialize(
            self.subindex
        )
        return _SDCPCodec.serialize_frame(
            SDCPOpcode.READ, SDCPFlag.NONE, self.transaction_id, payload
        )


@dataclass(frozen=True, repr=False)
class SDCPWriteRequest(_SDCPMessage):
    """An SDCP Write request."""

    index: int
    subindex: int
    value: bytes

    def __bytes__(self) -> bytes:
        """Serialize this Write request.

        Returns:
            The binary SDCP frame.

        Raises:
            TypeError: If the value payload is not bytes.
            ValueError: If the value payload is empty.

        """
        if not isinstance(self.value, bytes):
            raise TypeError("value must be bytes")
        if not self.value:
            raise ValueError("Write requests require a value payload")
        payload = (
            _SDCPFields.INDEX.serialize(self.index)
            + _SDCPFields.SUBINDEX.serialize(self.subindex)
            + self.value
        )
        return _SDCPCodec.serialize_frame(
            SDCPOpcode.WRITE,
            SDCPFlag.NONE,
            self.transaction_id,
            payload,
        )


@dataclass(frozen=True, repr=False)
class SDCPIdentificationResponse(_SDCPMessage):
    """An SDCP Identification response."""

    protocol_version: int
    profile_flags: SDCPProfileFlags
    device_mode: SDCPDeviceMode
    serial_number: int
    product_code: int
    revision_number: int

    def __post_init__(self) -> None:
        """Validate and normalize the protocol enum fields.

        Raises:
            TypeError: If a protocol field is not an integer.
            ValueError: If a Device Mode or reserved Profile Flags value is invalid.

        """
        device_mode_value = int.from_bytes(
            _SDCPFields.DEVICE_MODE.serialize(self.device_mode), _SDCP_BYTE_ORDER
        )
        try:
            device_mode = SDCPDeviceMode(device_mode_value)
        except ValueError as error:
            raise ValueError(
                f"Identification response has an unknown device mode: 0x{device_mode_value:02X}"
            ) from error
        object.__setattr__(self, "device_mode", device_mode)

        profile_flags_value = int.from_bytes(
            _SDCPFields.PROFILE_FLAGS.serialize(self.profile_flags), _SDCP_BYTE_ORDER
        )
        if profile_flags_value & _SDCP_PROFILE_FLAGS_RESERVED_MASK:
            raise ValueError(
                "Identification response has reserved profile flag bits set: "
                f"0x{profile_flags_value:04X}"
            )
        object.__setattr__(self, "profile_flags", SDCPProfileFlags(profile_flags_value))

    def __bytes__(self) -> bytes:
        """Serialize this Identification response.

        Returns:
            The binary SDCP frame.

        """
        payload = (
            _SDCPFields.PROTOCOL_VERSION.serialize(self.protocol_version)
            + _SDCPFields.PROFILE_FLAGS.serialize(self.profile_flags)
            + _SDCPFields.DEVICE_MODE.serialize(self.device_mode)
            + _SDCPFields.SERIAL_NUMBER.serialize(self.serial_number)
            + _SDCPFields.PRODUCT_CODE.serialize(self.product_code)
            + _SDCPFields.REVISION_NUMBER.serialize(self.revision_number)
        )
        return _SDCPCodec.serialize_frame(
            SDCPOpcode.IDENTIFICATION, SDCPFlag.REPLY, self.transaction_id, payload
        )


@dataclass(frozen=True, repr=False)
class SDCPReadResponse(_SDCPMessage):
    """An SDCP Read response with raw register value bytes."""

    value: bytes

    def __bytes__(self) -> bytes:
        """Serialize this Read response.

        Returns:
            The binary SDCP frame.

        Raises:
            TypeError: If the value payload is not bytes.

        """
        if not isinstance(self.value, bytes):
            raise TypeError("value must be bytes")
        return _SDCPCodec.serialize_frame(
            SDCPOpcode.READ,
            SDCPFlag.REPLY,
            self.transaction_id,
            self.value,
        )


@dataclass(frozen=True, repr=False)
class SDCPWriteResponse(_SDCPMessage):
    """An SDCP Write response."""

    def __bytes__(self) -> bytes:
        """Serialize this Write response.

        Returns:
            The binary SDCP frame.

        """
        return _SDCPCodec.serialize_frame(SDCPOpcode.WRITE, SDCPFlag.REPLY, self.transaction_id)


@dataclass(frozen=True, repr=False)
class SDCPErrorResponse(_SDCPMessage):
    """Abstract base class for operation-specific SDCP error responses."""

    error_code: int


@dataclass(frozen=True, repr=False)
class SDCPIdentificationResponseError(SDCPErrorResponse):
    """An SDCP Identification error response."""

    def __bytes__(self) -> bytes:
        """Serialize this Identification error response.

        Returns:
            The binary SDCP frame.

        """
        payload = _SDCPFields.ERROR_CODE.serialize(self.error_code)
        return _SDCPCodec.serialize_frame(
            SDCPOpcode.IDENTIFICATION,
            SDCPFlag.REPLY | SDCPFlag.ERROR,
            self.transaction_id,
            payload,
        )


@dataclass(frozen=True, repr=False)
class SDCPReadResponseError(SDCPErrorResponse):
    """An SDCP Read error response."""

    def __bytes__(self) -> bytes:
        """Serialize this Read error response.

        Returns:
            The binary SDCP frame.

        """
        payload = _SDCPFields.ERROR_CODE.serialize(self.error_code)
        return _SDCPCodec.serialize_frame(
            SDCPOpcode.READ, SDCPFlag.REPLY | SDCPFlag.ERROR, self.transaction_id, payload
        )


@dataclass(frozen=True, repr=False)
class SDCPWriteResponseError(SDCPErrorResponse):
    """An SDCP Write error response."""

    def __bytes__(self) -> bytes:
        """Serialize this Write error response.

        Returns:
            The binary SDCP frame.

        """
        payload = _SDCPFields.ERROR_CODE.serialize(self.error_code)
        return _SDCPCodec.serialize_frame(
            SDCPOpcode.WRITE, SDCPFlag.REPLY | SDCPFlag.ERROR, self.transaction_id, payload
        )


@dataclass(frozen=True, repr=False)
class SDCPUnknownFrame(_SDCPMessage):
    """An SDCP frame whose opcode or flags are not recognized."""

    opcode: int
    flags: int
    payload: bytes

    def __bytes__(self) -> bytes:
        """Serialize this unknown frame without altering its fields.

        Returns:
            The binary SDCP frame.

        """
        return _SDCPCodec.serialize_frame(
            self.opcode, self.flags, self.transaction_id, self.payload
        )


SDCPRequest = Union[
    SDCPIdentificationRequest,
    SDCPReadRequest,
    SDCPWriteRequest,
]

SDCPResponse = Union[
    SDCPIdentificationResponse,
    SDCPReadResponse,
    SDCPWriteResponse,
    SDCPErrorResponse,
]

SDCPMessage = Union[
    SDCPRequest,
    SDCPResponse,
    SDCPUnknownFrame,
]


class SDCPDeserializer:
    """Deserialize SDCP acyclic frames.

    SDCP uses a four-byte header with one-byte opcode and flags fields followed
    by a two-byte big-endian transaction ID. The operation-specific payload is
    preserved as raw bytes because its layout depends on the opcode.
    """

    HEADER_SIZE = _SDCPFields.OPCODE.size + _SDCPFields.FLAGS.size + _SDCPFields.TRANSACTION_ID.size

    @classmethod
    def deserialize(cls, frame: bytes) -> SDCPMessage:
        """Deserialize an SDCP acyclic frame.

        Args:
            frame: The UDP payload containing an SDCP acyclic frame.

        Returns:
            The decoded SDCP frame.

        Raises:
            TypeError: If the frame is not bytes.
            ValueError: If the frame is shorter than the four-byte SDCP header
                or a recognized frame has an invalid payload layout.

        """
        reader = _SDCPPayloadReader(frame)
        if len(frame) < cls.HEADER_SIZE:
            raise ValueError("SDCP frame must include a four-byte header")

        opcode = reader.read_uint(_SDCPFields.OPCODE)
        flags = reader.read_uint(_SDCPFields.FLAGS)
        transaction_id = reader.read_uint(_SDCPFields.TRANSACTION_ID)
        payload = reader.read_remaining()
        if flags == SDCPFlag.REPLY | SDCPFlag.ERROR:
            return cls._deserialize_error_response(opcode, transaction_id, payload)
        if flags == SDCPFlag.NONE:
            return cls._deserialize_request(opcode, transaction_id, payload)
        if flags == SDCPFlag.REPLY:
            return cls._deserialize_success_response(opcode, transaction_id, payload)

        return SDCPUnknownFrame(transaction_id, opcode, flags, payload)

    @classmethod
    def _deserialize_request(cls, opcode: int, transaction_id: int, payload: bytes) -> SDCPMessage:
        """Deserialize an SDCP request into its specific message type.

        Returns:
            A specialized request message or an unknown frame.

        Raises:
            ValueError: If a recognized request payload is malformed.

        """
        try:
            operation = SDCPOpcode(opcode)
        except ValueError:
            return SDCPUnknownFrame(transaction_id, opcode, SDCPFlag.NONE, payload)

        reader = _SDCPPayloadReader(payload)
        if operation == SDCPOpcode.IDENTIFICATION:
            reader.ensure_end()
            return SDCPIdentificationRequest(transaction_id)
        if operation == SDCPOpcode.READ:
            index = reader.read_uint(_SDCPFields.INDEX)
            subindex = reader.read_uint(_SDCPFields.SUBINDEX)
            reader.ensure_end()
            return SDCPReadRequest(transaction_id, index, subindex)
        if operation == SDCPOpcode.WRITE:
            index = reader.read_uint(_SDCPFields.INDEX)
            subindex = reader.read_uint(_SDCPFields.SUBINDEX)
            value = reader.read_remaining()
            if not value:
                raise ValueError("Write requests require a value payload")
            return SDCPWriteRequest(transaction_id, index, subindex, value)

    @classmethod
    def _deserialize_success_response(
        cls, opcode: int, transaction_id: int, payload: bytes
    ) -> SDCPMessage:
        """Deserialize a successful SDCP response into its specific message type.

        Returns:
            A specialized response message or an unknown frame.

        Raises:
            ValueError: If a recognized response payload is malformed.

        """
        try:
            operation = SDCPOpcode(opcode)
        except ValueError:
            return SDCPUnknownFrame(transaction_id, opcode, SDCPFlag.REPLY, payload)

        if operation == SDCPOpcode.IDENTIFICATION:
            return cls._deserialize_identification_response(transaction_id, payload)
        if operation == SDCPOpcode.READ:
            return SDCPReadResponse(transaction_id, payload)
        if operation == SDCPOpcode.WRITE:
            _SDCPPayloadReader(payload).ensure_end()
            return SDCPWriteResponse(transaction_id)

    @classmethod
    def _deserialize_error_response(
        cls, opcode: int, transaction_id: int, payload: bytes
    ) -> SDCPMessage:
        """Deserialize an SDCP error response.

        Returns:
            The specialized error response.

        Raises:
            ValueError: If the error payload is not a 2-byte error code.

        """
        try:
            operation = SDCPOpcode(opcode)
        except ValueError:
            return SDCPUnknownFrame(
                transaction_id, opcode, SDCPFlag.REPLY | SDCPFlag.ERROR, payload
            )

        reader = _SDCPPayloadReader(payload)
        error_code = reader.read_uint(_SDCPFields.ERROR_CODE)
        reader.ensure_end()
        if operation == SDCPOpcode.IDENTIFICATION:
            return SDCPIdentificationResponseError(transaction_id, error_code)
        if operation == SDCPOpcode.READ:
            return SDCPReadResponseError(transaction_id, error_code)
        if operation == SDCPOpcode.WRITE:
            return SDCPWriteResponseError(transaction_id, error_code)

    @classmethod
    def _deserialize_identification_response(
        cls, transaction_id: int, payload: bytes
    ) -> SDCPIdentificationResponse:
        """Deserialize the fixed-width Identification response payload.

        Returns:
            The parsed Identification response.

        Raises:
            ValueError: If the payload is not the fixed 16-byte layout or
                contains a reserved profile flag or device mode value.

        """
        reader = _SDCPPayloadReader(payload)
        response = SDCPIdentificationResponse(
            transaction_id,
            reader.read_uint(_SDCPFields.PROTOCOL_VERSION),
            reader.read_uint(_SDCPFields.PROFILE_FLAGS),
            reader.read_uint(_SDCPFields.DEVICE_MODE),
            reader.read_uint(_SDCPFields.SERIAL_NUMBER),
            reader.read_uint(_SDCPFields.PRODUCT_CODE),
            reader.read_uint(_SDCPFields.REVISION_NUMBER),
        )
        reader.ensure_end()
        return response
