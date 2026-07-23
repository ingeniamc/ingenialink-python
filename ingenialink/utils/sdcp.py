"""Serialization utilities for Servo Drives Control Protocol frames."""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import IntEnum, IntFlag
from typing import ClassVar, Literal, Union


class SDCPOpcode(IntEnum):
    """Opcodes defined by the SDCP acyclic communication protocol."""

    IDENTIFICATION = 0x01
    READ = 0x02
    WRITE = 0x03
    SUBSCRIBE = 0x04
    UNSUBSCRIBE = 0x05


class SDCPFlag(IntFlag):
    """Flags defined by the SDCP acyclic communication protocol."""

    NONE = 0x00
    REPLY = 0x01
    ERROR = 0x02


class SDCPSubscriptionMode(IntEnum):
    """Subscription modes defined by the SDCP acyclic communication protocol."""

    PERIODIC = 0x01
    EVENT = 0x02


_SDCP_BYTE_ORDER: Literal["big"] = "big"


@dataclass(frozen=True)
class _SDCPField:
    """Metadata for a fixed-width SDCP field."""

    size: int

    @property
    def hex_width(self) -> int:
        """Return the field's hexadecimal display width."""
        return self.size * 2

    @property
    def maximum_value(self) -> int:
        """Return the largest unsigned value that fits in the field."""
        return (1 << (self.size * 8)) - 1


class _SDCPFields:
    """Fixed-width SDCP field definitions."""

    OPCODE = _SDCPField(1)
    FLAGS = _SDCPField(1)
    TRANSACTION_ID = _SDCPField(2)
    INDEX = _SDCPField(2)
    SUBINDEX = _SDCPField(1)
    SUBSCRIPTION_ID = _SDCPField(2)
    CYCLIC_TIME_MS = _SDCPField(2)
    MESSAGE_COUNT = _SDCPField(2)
    ERROR_CODE = _SDCPField(4)
    PROTOCOL_VERSION = _SDCPField(1)
    SERIAL_NUMBER = _SDCPField(4)
    PRODUCT_CODE = _SDCPField(4)
    REVISION_NUMBER = _SDCPField(4)
    SUBSCRIPTION_MODE = _SDCPField(1)


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


@dataclass(frozen=True, repr=False)
class _SDCPMessageRepresentation:
    """Base class for typed SDCP messages."""

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
            elif message_field.name == "opcode":
                try:
                    formatted_value = f"SDCPOpcode.{SDCPOpcode(value).name}"
                except ValueError:
                    formatted_value = f"0x{value:02X}"
            elif isinstance(value, int):
                protocol_field = getattr(_SDCPFields, message_field.name.upper(), None)
                width = protocol_field.hex_width if protocol_field else 0
                formatted_value = f"0x{value:0{width}X}" if width else f"0x{value:X}"
            else:
                formatted_value = repr(value)
            formatted_fields.append(f"{message_field.name}={formatted_value}")

        return f"{type(self).__name__}({', '.join(formatted_fields)})"


@dataclass(frozen=True, repr=False)
class SDCPIdentificationRequest(_SDCPMessageRepresentation):
    """An SDCP Identification request."""

    transaction_id: int


@dataclass(frozen=True, repr=False)
class SDCPReadRequest(_SDCPMessageRepresentation):
    """An SDCP Read request."""

    transaction_id: int
    index: int
    subindex: int


@dataclass(frozen=True, repr=False)
class SDCPWriteRequest(_SDCPMessageRepresentation):
    """An SDCP Write request."""

    transaction_id: int
    index: int
    subindex: int
    value: bytes


@dataclass(frozen=True, repr=False)
class SDCPPeriodicSubscriptionRequest(_SDCPMessageRepresentation):
    """An SDCP periodic Subscribe request."""

    transaction_id: int
    index: int
    subindex: int
    cyclic_time_ms: int
    message_count: int


@dataclass(frozen=True, repr=False)
class SDCPEventSubscriptionRequest(_SDCPMessageRepresentation):
    """An SDCP event-based Subscribe request."""

    transaction_id: int
    index: int
    subindex: int
    message_count: int


@dataclass(frozen=True, repr=False)
class SDCPUnsubscribeRequest(_SDCPMessageRepresentation):
    """An SDCP Unsubscribe request."""

    transaction_id: int
    subscription_id: int


@dataclass(frozen=True, repr=False)
class SDCPIdentificationResponse(_SDCPMessageRepresentation):
    """An SDCP Identification response."""

    transaction_id: int
    protocol_version: int
    serial_number: int
    product_code: int
    revision_number: int


@dataclass(frozen=True, repr=False)
class SDCPReadResponse(_SDCPMessageRepresentation):
    """An SDCP Read response with raw register value bytes."""

    transaction_id: int
    value: bytes


@dataclass(frozen=True, repr=False)
class SDCPWriteResponse(_SDCPMessageRepresentation):
    """An SDCP Write response."""

    transaction_id: int


@dataclass(frozen=True, repr=False)
class SDCPSubscribeResponse(_SDCPMessageRepresentation):
    """An SDCP Subscribe response containing a subscription identifier."""

    transaction_id: int
    subscription_id: int


@dataclass(frozen=True, repr=False)
class SDCPUnsubscribeResponse(_SDCPMessageRepresentation):
    """An SDCP Unsubscribe response."""

    transaction_id: int


@dataclass(frozen=True, repr=False)
class SDCPErrorResponse(_SDCPMessageRepresentation):
    """Base class for operation-specific SDCP error responses."""

    transaction_id: int
    error_code: int


@dataclass(frozen=True, repr=False)
class SDCPIdentificationResponseError(SDCPErrorResponse):
    """An SDCP Identification error response."""


@dataclass(frozen=True, repr=False)
class SDCPReadResponseError(SDCPErrorResponse):
    """An SDCP Read error response."""


@dataclass(frozen=True, repr=False)
class SDCPWriteResponseError(SDCPErrorResponse):
    """An SDCP Write error response."""


@dataclass(frozen=True, repr=False)
class SDCPSubscribeResponseError(SDCPErrorResponse):
    """An SDCP Subscribe error response."""


@dataclass(frozen=True, repr=False)
class SDCPUnsubscribeResponseError(SDCPErrorResponse):
    """An SDCP Unsubscribe error response."""


@dataclass(frozen=True, repr=False)
class SDCPUnknownFrame(_SDCPMessageRepresentation):
    """An SDCP frame whose opcode or flags are not recognized."""

    opcode: int
    flags: int
    transaction_id: int
    payload: bytes


SDCPMessage = Union[
    SDCPIdentificationRequest,
    SDCPReadRequest,
    SDCPWriteRequest,
    SDCPPeriodicSubscriptionRequest,
    SDCPEventSubscriptionRequest,
    SDCPUnsubscribeRequest,
    SDCPIdentificationResponse,
    SDCPReadResponse,
    SDCPWriteResponse,
    SDCPSubscribeResponse,
    SDCPUnsubscribeResponse,
    SDCPErrorResponse,
    SDCPUnknownFrame,
]


class SDCPSerializer:
    """Serialize and deserialize SDCP acyclic frames.

    SDCP uses a four-byte header with one-byte opcode and flags fields followed
    by a two-byte big-endian transaction ID. The operation-specific payload is
    preserved as raw bytes because its layout depends on the opcode.
    """

    HEADER_SIZE = _SDCPFields.OPCODE.size + _SDCPFields.FLAGS.size + _SDCPFields.TRANSACTION_ID.size
    _EMPTY_RESPONSE_TYPES: ClassVar[
        dict[SDCPOpcode, type[SDCPWriteResponse] | type[SDCPUnsubscribeResponse]]
    ] = {
        SDCPOpcode.WRITE: SDCPWriteResponse,
        SDCPOpcode.UNSUBSCRIBE: SDCPUnsubscribeResponse,
    }
    _ERROR_RESPONSE_TYPES: ClassVar[dict[SDCPOpcode, type[SDCPErrorResponse]]] = {
        SDCPOpcode.IDENTIFICATION: SDCPIdentificationResponseError,
        SDCPOpcode.READ: SDCPReadResponseError,
        SDCPOpcode.WRITE: SDCPWriteResponseError,
        SDCPOpcode.SUBSCRIBE: SDCPSubscribeResponseError,
        SDCPOpcode.UNSUBSCRIBE: SDCPUnsubscribeResponseError,
    }

    @classmethod
    def serialize_identification_request(cls, transaction_id: int) -> bytes:
        """Serialize an Identification request.

        Args:
            transaction_id: Request identifier in the range 0 to 65535.

        Returns:
            The big-endian SDCP frame ready to send as a UDP payload.

        """
        return cls._serialize_frame(SDCPOpcode.IDENTIFICATION, SDCPFlag.NONE, transaction_id)

    @classmethod
    def serialize_read_request(cls, transaction_id: int, index: int, subindex: int) -> bytes:
        """Serialize a Read request.

        Args:
            transaction_id: Request identifier in the range 0 to 65535.
            index: Dictionary index to read.
            subindex: Dictionary subindex to read.

        Returns:
            The big-endian SDCP frame ready to send as a UDP payload.

        """
        return cls._serialize_dictionary_request(SDCPOpcode.READ, transaction_id, index, subindex)

    @classmethod
    def serialize_write_request(
        cls, transaction_id: int, index: int, subindex: int, value: bytes
    ) -> bytes:
        """Serialize a Write request.

        Args:
            transaction_id: Request identifier in the range 0 to 65535.
            index: Dictionary index to write.
            subindex: Dictionary subindex to write.
            value: Encoded value bytes to write.

        Returns:
            The big-endian SDCP frame ready to send as a UDP payload.

        Raises:
            TypeError: If the value is not bytes.
            ValueError: If the value is empty.

        """
        cls._validate_bytes("value", value)
        if not value:
            raise ValueError("Write requests require a value payload")

        return cls._serialize_dictionary_request(
            SDCPOpcode.WRITE, transaction_id, index, subindex, value
        )

    @classmethod
    def serialize_periodic_subscription_request(
        cls,
        transaction_id: int,
        index: int,
        subindex: int,
        cyclic_time_ms: int,
        message_count: int,
    ) -> bytes:
        """Serialize a periodic Subscribe request.

        Args:
            transaction_id: Request identifier in the range 0 to 65535.
            index: Dictionary index to subscribe to.
            subindex: Dictionary subindex to subscribe to.
            cyclic_time_ms: Periodic cycle time in milliseconds.
            message_count: Maximum notifications before expiration.

        Returns:
            The big-endian SDCP frame ready to send as a UDP payload.

        """
        payload = b"".join((
            cls._serialize_uint(_SDCPFields.SUBSCRIPTION_MODE, SDCPSubscriptionMode.PERIODIC),
            cls._serialize_uint(_SDCPFields.CYCLIC_TIME_MS, cyclic_time_ms),
            cls._serialize_uint(_SDCPFields.MESSAGE_COUNT, message_count),
        ))
        return cls._serialize_dictionary_request(
            SDCPOpcode.SUBSCRIBE, transaction_id, index, subindex, payload
        )

    @classmethod
    def serialize_event_subscription_request(
        cls, transaction_id: int, index: int, subindex: int, message_count: int
    ) -> bytes:
        """Serialize an event-based Subscribe request.

        Args:
            transaction_id: Request identifier in the range 0 to 65535.
            index: Dictionary index to subscribe to.
            subindex: Dictionary subindex to subscribe to.
            message_count: Maximum notifications before expiration.

        Returns:
            The big-endian SDCP frame ready to send as a UDP payload.

        """
        payload = cls._serialize_uint(
            _SDCPFields.SUBSCRIPTION_MODE, SDCPSubscriptionMode.EVENT
        ) + cls._serialize_uint(_SDCPFields.MESSAGE_COUNT, message_count)
        return cls._serialize_dictionary_request(
            SDCPOpcode.SUBSCRIBE, transaction_id, index, subindex, payload
        )

    @classmethod
    def serialize_unsubscribe_request(cls, transaction_id: int, subscription_id: int) -> bytes:
        """Serialize an Unsubscribe request.

        Args:
            transaction_id: Request identifier in the range 0 to 65535.
            subscription_id: Identifier of the subscription to cancel.

        Returns:
            The big-endian SDCP frame ready to send as a UDP payload.

        """
        return cls._serialize_frame(
            SDCPOpcode.UNSUBSCRIBE,
            SDCPFlag.NONE,
            transaction_id,
            cls._serialize_uint(_SDCPFields.SUBSCRIPTION_ID, subscription_id),
        )

    @classmethod
    def serialize_success_response(
        cls, opcode: int, transaction_id: int, payload: bytes = b""
    ) -> bytes:
        """Serialize a successful response.

        Args:
            opcode: Opcode of the request being answered.
            transaction_id: Identifier of the request being answered.
            payload: Optional operation-specific response bytes.

        Returns:
            The big-endian SDCP response frame.

        """
        return cls._serialize_frame(opcode, SDCPFlag.REPLY, transaction_id, payload)

    @classmethod
    def serialize_error_response(cls, opcode: int, transaction_id: int, error_code: int) -> bytes:
        """Serialize an error response.

        Args:
            opcode: Opcode of the request being answered.
            transaction_id: Identifier of the request being answered.
            error_code: Unsigned 32-bit protocol error code.

        Returns:
            The big-endian SDCP error response frame.

        """
        return cls._serialize_frame(
            opcode,
            SDCPFlag.REPLY | SDCPFlag.ERROR,
            transaction_id,
            cls._serialize_uint(_SDCPFields.ERROR_CODE, error_code),
        )

    @classmethod
    def _serialize_dictionary_request(
        cls,
        opcode: SDCPOpcode,
        transaction_id: int,
        index: int,
        subindex: int,
        payload: bytes = b"",
    ) -> bytes:
        """Serialize a request whose payload begins with a dictionary address.

        Returns:
            The big-endian SDCP request frame.

        """
        address = cls._serialize_uint(_SDCPFields.INDEX, index) + cls._serialize_uint(
            _SDCPFields.SUBINDEX, subindex
        )
        return cls._serialize_frame(opcode, SDCPFlag.NONE, transaction_id, address + payload)

    @classmethod
    def _serialize_frame(
        cls, opcode: int, flags: int, transaction_id: int, payload: bytes = b""
    ) -> bytes:
        """Serialize the common SDCP header and raw operation payload.

        Returns:
            The big-endian SDCP frame.

        Raises:
            TypeError: If the payload is not bytes.
            ValueError: If a header field does not fit its protocol-defined size.

        """
        cls._validate_bytes("payload", payload)
        header = b"".join((
            cls._serialize_uint(_SDCPFields.OPCODE, opcode),
            cls._serialize_uint(_SDCPFields.FLAGS, flags),
            cls._serialize_uint(_SDCPFields.TRANSACTION_ID, transaction_id),
        ))
        return header + payload

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

        return SDCPUnknownFrame(opcode, flags, transaction_id, payload)

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
            return SDCPUnknownFrame(opcode, SDCPFlag.NONE, transaction_id, payload)

        reader = _SDCPPayloadReader(payload)
        if operation == SDCPOpcode.IDENTIFICATION:
            reader.ensure_end()
            return SDCPIdentificationRequest(transaction_id)
        if operation == SDCPOpcode.READ:
            index, subindex = cls._deserialize_dictionary_address(reader)
            reader.ensure_end()
            return SDCPReadRequest(transaction_id, index, subindex)
        if operation == SDCPOpcode.WRITE:
            index, subindex = cls._deserialize_dictionary_address(reader)
            value = reader.read_remaining()
            if not value:
                raise ValueError("Write requests require a value payload")
            return SDCPWriteRequest(transaction_id, index, subindex, value)
        if operation == SDCPOpcode.SUBSCRIBE:
            return cls._deserialize_subscription_request(transaction_id, reader)
        if operation == SDCPOpcode.UNSUBSCRIBE:
            subscription_id = reader.read_uint(_SDCPFields.SUBSCRIPTION_ID)
            reader.ensure_end()
            return SDCPUnsubscribeRequest(
                transaction_id,
                subscription_id,
            )

        return SDCPUnknownFrame(opcode, SDCPFlag.NONE, transaction_id, payload)

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
            return SDCPUnknownFrame(opcode, SDCPFlag.REPLY, transaction_id, payload)

        if operation == SDCPOpcode.IDENTIFICATION:
            return cls._deserialize_identification_response(transaction_id, payload)
        if operation == SDCPOpcode.READ:
            return SDCPReadResponse(transaction_id, payload)
        if operation == SDCPOpcode.SUBSCRIBE:
            # Subscribe notifications cannot yet be distinguished from initial Subscribe replies.
            return cls._deserialize_subscribe_response(transaction_id, payload)

        response_type = cls._EMPTY_RESPONSE_TYPES.get(operation)
        if response_type is not None:
            return cls._deserialize_empty_response(transaction_id, payload, response_type)

        return SDCPUnknownFrame(opcode, SDCPFlag.REPLY, transaction_id, payload)

    @classmethod
    def _deserialize_subscribe_response(
        cls, transaction_id: int, payload: bytes
    ) -> SDCPSubscribeResponse:
        """Deserialize a Subscribe response containing a subscription identifier.

        Returns:
            The parsed Subscribe response.

        """
        reader = _SDCPPayloadReader(payload)
        subscription_id = reader.read_uint(_SDCPFields.SUBSCRIPTION_ID)
        reader.ensure_end()
        return SDCPSubscribeResponse(transaction_id, subscription_id)

    @staticmethod
    def _deserialize_empty_response(
        transaction_id: int,
        payload: bytes,
        response_type: type[SDCPWriteResponse] | type[SDCPUnsubscribeResponse],
    ) -> SDCPWriteResponse | SDCPUnsubscribeResponse:
        """Deserialize a response whose payload must be empty.

        Returns:
            The parsed empty response.

        Raises:
            ValueError: If the response contains a payload.

        """
        _SDCPPayloadReader(payload).ensure_end()
        return response_type(transaction_id)

    @classmethod
    def _deserialize_error_response(
        cls, opcode: int, transaction_id: int, payload: bytes
    ) -> SDCPMessage:
        """Deserialize an SDCP error response.

        Returns:
            The specialized error response.

        Raises:
            ValueError: If the error payload is not a 32-bit error code.

        """
        try:
            operation = SDCPOpcode(opcode)
        except ValueError:
            return SDCPUnknownFrame(
                opcode, SDCPFlag.REPLY | SDCPFlag.ERROR, transaction_id, payload
            )

        reader = _SDCPPayloadReader(payload)
        error_code = reader.read_uint(_SDCPFields.ERROR_CODE)
        reader.ensure_end()
        response_type = cls._ERROR_RESPONSE_TYPES[operation]
        return response_type(transaction_id, error_code)

    @classmethod
    def _deserialize_identification_response(
        cls, transaction_id: int, payload: bytes
    ) -> SDCPIdentificationResponse:
        """Deserialize the fixed-width Identification response payload.

        Returns:
            The parsed Identification response.

        Raises:
            ValueError: If the payload is not the fixed 13-byte layout. SDCP
                Identification responses with a 9-byte firmware layout are not
                supported because the public message requires a revision number.

        """
        reader = _SDCPPayloadReader(payload)
        response = SDCPIdentificationResponse(
            transaction_id,
            reader.read_uint(_SDCPFields.PROTOCOL_VERSION),
            reader.read_uint(_SDCPFields.SERIAL_NUMBER),
            reader.read_uint(_SDCPFields.PRODUCT_CODE),
            reader.read_uint(_SDCPFields.REVISION_NUMBER),
        )
        reader.ensure_end()
        return response

    @classmethod
    def _deserialize_subscription_request(
        cls, transaction_id: int, reader: _SDCPPayloadReader
    ) -> SDCPMessage:
        """Deserialize a Subscribe request into its mode-specific message type.

        Returns:
            A periodic or event-based subscription request.

        Raises:
            ValueError: If the subscription payload is malformed.

        """
        index, subindex = cls._deserialize_dictionary_address(reader)
        mode_value = reader.read_uint(_SDCPFields.SUBSCRIPTION_MODE)
        try:
            mode = SDCPSubscriptionMode(mode_value)
        except ValueError as error:
            raise ValueError(
                f"Subscribe request has an unknown subscription mode: 0x{mode_value:02X}"
            ) from error

        if mode == SDCPSubscriptionMode.PERIODIC:
            request: SDCPPeriodicSubscriptionRequest | SDCPEventSubscriptionRequest = (
                SDCPPeriodicSubscriptionRequest(
                    transaction_id,
                    index,
                    subindex,
                    reader.read_uint(_SDCPFields.CYCLIC_TIME_MS),
                    reader.read_uint(_SDCPFields.MESSAGE_COUNT),
                )
            )
        else:
            request = SDCPEventSubscriptionRequest(
                transaction_id,
                index,
                subindex,
                reader.read_uint(_SDCPFields.MESSAGE_COUNT),
            )
        reader.ensure_end()
        return request

    @staticmethod
    def _deserialize_dictionary_address(reader: _SDCPPayloadReader) -> tuple[int, int]:
        """Deserialize a dictionary address from the current payload position.

        Returns:
            The dictionary index and subindex.

        Raises:
            ValueError: If the payload cannot contain the address.

        """
        return reader.read_uint(_SDCPFields.INDEX), reader.read_uint(_SDCPFields.SUBINDEX)

    @staticmethod
    def _validate_uint(field: _SDCPField, value: int) -> None:
        """Validate that an integer fits in an unsigned protocol field.

        Raises:
            TypeError: If the value is not an integer or is a boolean.
            ValueError: If the integer cannot fit in the field.

        """
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"Value must be an integer for a {field.size}-byte field")
        if not 0 <= value <= field.maximum_value:
            raise ValueError(f"Value must be in the range 0 to {field.maximum_value}")

    @classmethod
    def _serialize_uint(cls, field: _SDCPField, value: int) -> bytes:
        """Serialize an unsigned SDCP field using the protocol byte order.

        Returns:
            The fixed-width big-endian representation of the field.

        """
        cls._validate_uint(field, value)
        return value.to_bytes(field.size, _SDCP_BYTE_ORDER)

    @staticmethod
    def _validate_bytes(field_name: str, value: bytes) -> None:
        """Validate a raw protocol byte payload.

        Raises:
            TypeError: If the value is not bytes.

        """
        if not isinstance(value, bytes):
            raise TypeError(f"{field_name} must be bytes")
