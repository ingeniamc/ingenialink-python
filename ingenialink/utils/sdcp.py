"""Serialization utilities for Servo Drives Control Protocol frames."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import IntEnum, IntFlag
from typing import Literal, Union


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


@dataclass(frozen=True)
class _SDCPField:
    """Metadata for a fixed-width SDCP field."""

    size: int
    hex_width: int = field(init=False)
    maximum_value: int = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "hex_width", self.size * 2)
        object.__setattr__(self, "maximum_value", (1 << (self.size * 8)) - 1)


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
class _SDCPErrorResponse(_SDCPMessageRepresentation):
    """Base class for operation-specific SDCP error responses."""

    transaction_id: int
    error_code: int


@dataclass(frozen=True, repr=False)
class SDCPIdentificationResponseError(_SDCPErrorResponse):
    """An SDCP Identification error response."""


@dataclass(frozen=True, repr=False)
class SDCPReadResponseError(_SDCPErrorResponse):
    """An SDCP Read error response."""


@dataclass(frozen=True, repr=False)
class SDCPWriteResponseError(_SDCPErrorResponse):
    """An SDCP Write error response."""


@dataclass(frozen=True, repr=False)
class SDCPSubscribeResponseError(_SDCPErrorResponse):
    """An SDCP Subscribe error response."""


@dataclass(frozen=True, repr=False)
class SDCPUnsubscribeResponseError(_SDCPErrorResponse):
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
    SDCPIdentificationResponseError,
    SDCPReadResponseError,
    SDCPWriteResponseError,
    SDCPSubscribeResponseError,
    SDCPUnsubscribeResponseError,
    SDCPUnknownFrame,
]


class SDCPSerializer:
    """Serialize and deserialize SDCP acyclic frames.

    SDCP uses a four-byte header with one-byte opcode and flags fields followed
    by a two-byte big-endian transaction ID. The operation-specific payload is
    preserved as raw bytes because its layout depends on the opcode.
    """

    BYTE_ORDER: Literal["big"] = "big"
    HEADER_SIZE = _SDCPFields.OPCODE.size + _SDCPFields.FLAGS.size + _SDCPFields.TRANSACTION_ID.size

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
            ValueError: If the frame is shorter than the four-byte SDCP header
                or a recognized frame has an invalid payload layout.

        """
        if len(frame) < cls.HEADER_SIZE:
            raise ValueError("SDCP frame must include a four-byte header")

        opcode = frame[0]
        flags = frame[1]
        payload = frame[cls.HEADER_SIZE :]
        transaction_id = cls._deserialize_uint(
            _SDCPFields.TRANSACTION_ID,
            frame[_SDCPFields.OPCODE.size + _SDCPFields.FLAGS.size : cls.HEADER_SIZE],
        )
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

        if operation == SDCPOpcode.IDENTIFICATION:
            cls._validate_payload_size(payload, 0, "Identification request")
            return SDCPIdentificationRequest(transaction_id)
        if operation == SDCPOpcode.READ:
            cls._validate_payload_size(payload, 3, "Read request")
            index, subindex = cls._deserialize_dictionary_address(payload, "Read request", 0)
            return SDCPReadRequest(transaction_id, index, subindex)
        if operation == SDCPOpcode.WRITE:
            index, subindex = cls._deserialize_dictionary_address(payload, "Write request", 1)
            return SDCPWriteRequest(transaction_id, index, subindex, payload[3:])
        if operation == SDCPOpcode.SUBSCRIBE:
            return cls._deserialize_subscription_request(transaction_id, payload)
        if operation == SDCPOpcode.UNSUBSCRIBE:
            cls._validate_payload_size(
                payload, _SDCPFields.SUBSCRIPTION_ID.size, "Unsubscribe request"
            )
            return SDCPUnsubscribeRequest(
                transaction_id,
                cls._deserialize_uint(_SDCPFields.SUBSCRIPTION_ID, payload),
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
        if operation == SDCPOpcode.WRITE:
            cls._validate_payload_size(payload, 0, "Write response")
            return SDCPWriteResponse(transaction_id)
        if operation == SDCPOpcode.SUBSCRIBE:
            # Notification payloads cannot yet be distinguished from subscription replies.
            cls._validate_payload_size(
                payload, _SDCPFields.SUBSCRIPTION_ID.size, "Subscribe response"
            )
            return SDCPSubscribeResponse(
                transaction_id,
                cls._deserialize_uint(_SDCPFields.SUBSCRIPTION_ID, payload),
            )
        if operation == SDCPOpcode.UNSUBSCRIBE:
            cls._validate_payload_size(payload, 0, "Unsubscribe response")
            return SDCPUnsubscribeResponse(transaction_id)

        return SDCPUnknownFrame(opcode, SDCPFlag.REPLY, transaction_id, payload)

    @classmethod
    def _deserialize_error_response(
        cls, opcode: int, transaction_id: int, payload: bytes
    ) -> SDCPMessage:
        """Deserialize an SDCP error response.

        Returns:
            The specialized error response.

        Raises:
            ValueError: If the error payload is not a 32-bit error code.
            AssertionError: If the opcode is not a defined SDCP operation.

        """
        try:
            operation = SDCPOpcode(opcode)
        except ValueError:
            return SDCPUnknownFrame(
                opcode, SDCPFlag.REPLY | SDCPFlag.ERROR, transaction_id, payload
            )

        cls._validate_payload_size(payload, _SDCPFields.ERROR_CODE.size, "Error response")
        error_code = cls._deserialize_uint(_SDCPFields.ERROR_CODE, payload)
        if operation == SDCPOpcode.IDENTIFICATION:
            return SDCPIdentificationResponseError(transaction_id, error_code)
        if operation == SDCPOpcode.READ:
            return SDCPReadResponseError(transaction_id, error_code)
        if operation == SDCPOpcode.WRITE:
            return SDCPWriteResponseError(transaction_id, error_code)
        if operation == SDCPOpcode.SUBSCRIBE:
            return SDCPSubscribeResponseError(transaction_id, error_code)
        if operation == SDCPOpcode.UNSUBSCRIBE:
            return SDCPUnsubscribeResponseError(transaction_id, error_code)
        raise AssertionError(f"Unsupported SDCP opcode: {operation}")

    @classmethod
    def _deserialize_identification_response(
        cls, transaction_id: int, payload: bytes
    ) -> SDCPIdentificationResponse:
        """Deserialize the fixed-width Identification response payload.

        Returns:
            The parsed Identification response.

        Raises:
            ValueError: If the payload is not the fixed 13-byte layout.

        """
        fields = (
            _SDCPFields.PROTOCOL_VERSION,
            _SDCPFields.SERIAL_NUMBER,
            _SDCPFields.PRODUCT_CODE,
            _SDCPFields.REVISION_NUMBER,
        )
        cls._validate_payload_size(
            payload, sum(field.size for field in fields), "Identification response"
        )
        protocol_version_end = _SDCPFields.PROTOCOL_VERSION.size
        serial_number_end = protocol_version_end + _SDCPFields.SERIAL_NUMBER.size
        product_code_end = serial_number_end + _SDCPFields.PRODUCT_CODE.size
        return SDCPIdentificationResponse(
            transaction_id,
            cls._deserialize_uint(_SDCPFields.PROTOCOL_VERSION, payload[:protocol_version_end]),
            cls._deserialize_uint(
                _SDCPFields.SERIAL_NUMBER,
                payload[protocol_version_end:serial_number_end],
            ),
            cls._deserialize_uint(
                _SDCPFields.PRODUCT_CODE,
                payload[serial_number_end:product_code_end],
            ),
            cls._deserialize_uint(_SDCPFields.REVISION_NUMBER, payload[product_code_end:]),
        )

    @classmethod
    def _deserialize_subscription_request(cls, transaction_id: int, payload: bytes) -> SDCPMessage:
        """Deserialize a Subscribe request into its mode-specific message type.

        Returns:
            A periodic or event-based subscription request.

        Raises:
            ValueError: If the subscription payload is malformed.

        """
        index, subindex = cls._deserialize_dictionary_address(payload, "Subscribe request", 3)
        try:
            mode = SDCPSubscriptionMode(payload[3])
        except ValueError as error:
            raise ValueError("Subscribe request has an unknown subscription mode") from error

        if mode == SDCPSubscriptionMode.PERIODIC:
            cls._validate_payload_size(payload, 8, "Periodic Subscribe request")
            return SDCPPeriodicSubscriptionRequest(
                transaction_id,
                index,
                subindex,
                cls._deserialize_uint(_SDCPFields.CYCLIC_TIME_MS, payload[4:6]),
                cls._deserialize_uint(_SDCPFields.MESSAGE_COUNT, payload[6:8]),
            )

        cls._validate_payload_size(payload, 6, "Event Subscribe request")
        return SDCPEventSubscriptionRequest(
            transaction_id,
            index,
            subindex,
            cls._deserialize_uint(_SDCPFields.MESSAGE_COUNT, payload[4:6]),
        )

    @classmethod
    def _deserialize_dictionary_address(
        cls, payload: bytes, message_name: str, trailing_payload_size: int
    ) -> tuple[int, int]:
        """Deserialize an address prefix from a dictionary request payload.

        Returns:
            The dictionary index and subindex.

        Raises:
            ValueError: If the payload cannot contain the address and trailing fields.

        """
        minimum_size = _SDCPFields.INDEX.size + _SDCPFields.SUBINDEX.size + trailing_payload_size
        if len(payload) < minimum_size:
            raise ValueError(f"{message_name} payload is incomplete")
        return cls._deserialize_uint(_SDCPFields.INDEX, payload[:2]), payload[2]

    @staticmethod
    def _validate_payload_size(payload: bytes, expected_size: int, message_name: str) -> None:
        """Validate the exact payload size of a fixed-layout message.

        Raises:
            ValueError: If the payload size does not match the message layout.

        """
        if len(payload) != expected_size:
            raise ValueError(f"{message_name} payload must contain {expected_size} bytes")

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
        return value.to_bytes(field.size, cls.BYTE_ORDER)

    @classmethod
    def _deserialize_uint(cls, field: _SDCPField, value: bytes) -> int:
        """Deserialize an unsigned SDCP field using the protocol byte order.

        Returns:
            The decoded unsigned integer.

        Raises:
            ValueError: If the byte value is not the field's fixed width.

        """
        if len(value) != field.size:
            raise ValueError(f"Value must contain {field.size} bytes")
        return int.from_bytes(value, cls.BYTE_ORDER)

    @staticmethod
    def _validate_bytes(field_name: str, value: bytes) -> None:
        """Validate a raw protocol byte payload.

        Raises:
            TypeError: If the value is not bytes.

        """
        if not isinstance(value, bytes):
            raise TypeError(f"{field_name} must be bytes")
