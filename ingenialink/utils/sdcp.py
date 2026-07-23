"""Serialization utilities for Servo Drives Control Protocol frames."""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import IntEnum, IntFlag
from typing import Union


class SDCPOpcode(IntEnum):
    """Opcodes defined by the SDCP acyclic communication protocol."""

    IDENTIFY = 0x01
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


@dataclass(frozen=True, repr=False)
class _SDCPMessageRepresentation:
    """Base class for typed SDCP messages."""

    def __repr__(self) -> str:
        """Return a protocol-oriented representation using hexadecimal values.

        Returns:
            The message type and its fields formatted as protocol values.

        """
        field_widths = {
            "transaction_id": 4,
            "index": 4,
            "subindex": 2,
            "subscription_id": 4,
            "cyclic_time_ms": 4,
            "message_count": 4,
            "opcode": 2,
            "flags": 2,
            "error_code": 8,
        }
        formatted_fields = []
        for message_field in fields(self):
            value = getattr(self, message_field.name)
            if isinstance(value, bytes):
                formatted_value = f"0x{value.hex().upper()}"
            elif isinstance(value, int):
                formatted_value = f"0x{value:0{field_widths[message_field.name]}X}"
            else:
                formatted_value = repr(value)
            formatted_fields.append(f"{message_field.name}={formatted_value}")

        return f"{type(self).__name__}({', '.join(formatted_fields)})"


@dataclass(frozen=True, repr=False)
class SDCPIdentifyRequest(_SDCPMessageRepresentation):
    """An SDCP Identify request."""

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
class SDCPIdentifyResponse(_SDCPMessageRepresentation):
    """An SDCP Identify response with raw identification data."""

    transaction_id: int
    identification: bytes


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
    """An SDCP error response."""

    opcode: int
    transaction_id: int
    error_code: int


@dataclass(frozen=True, repr=False)
class SDCPUnknownFrame(_SDCPMessageRepresentation):
    """An SDCP frame whose opcode or flags are not recognized."""

    opcode: int
    flags: int
    transaction_id: int
    payload: bytes


SDCPMessage = Union[
    SDCPIdentifyRequest,
    SDCPReadRequest,
    SDCPWriteRequest,
    SDCPPeriodicSubscriptionRequest,
    SDCPEventSubscriptionRequest,
    SDCPUnsubscribeRequest,
    SDCPIdentifyResponse,
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

    HEADER_SIZE = 4
    OPCODE_SIZE = 1
    FLAGS_SIZE = 1
    TRANSACTION_ID_SIZE = 2

    @classmethod
    def serialize_identify_request(cls, transaction_id: int) -> bytes:
        """Serialize an Identify request.

        Args:
            transaction_id: Request identifier in the range 0 to 65535.

        Returns:
            The big-endian SDCP frame ready to send as a UDP payload.

        """
        return cls._serialize_frame(SDCPOpcode.IDENTIFY, SDCPFlag.NONE, transaction_id)

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
            ValueError: If the value is empty.

        """
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
        cls._validate_uint("cyclic_time_ms", cyclic_time_ms, cls.TRANSACTION_ID_SIZE)
        cls._validate_uint("message_count", message_count, cls.TRANSACTION_ID_SIZE)
        payload = b"".join((
            SDCPSubscriptionMode.PERIODIC.to_bytes(cls.OPCODE_SIZE, "big"),
            cyclic_time_ms.to_bytes(cls.TRANSACTION_ID_SIZE, "big"),
            message_count.to_bytes(cls.TRANSACTION_ID_SIZE, "big"),
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
        cls._validate_uint("message_count", message_count, cls.TRANSACTION_ID_SIZE)
        payload = SDCPSubscriptionMode.EVENT.to_bytes(
            cls.OPCODE_SIZE, "big"
        ) + message_count.to_bytes(cls.TRANSACTION_ID_SIZE, "big")
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
        cls._validate_uint("subscription_id", subscription_id, cls.TRANSACTION_ID_SIZE)
        return cls._serialize_frame(
            SDCPOpcode.UNSUBSCRIBE,
            SDCPFlag.NONE,
            transaction_id,
            subscription_id.to_bytes(cls.TRANSACTION_ID_SIZE, "big"),
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
        error_code_size = 4
        cls._validate_uint("error_code", error_code, error_code_size)
        return cls._serialize_frame(
            opcode,
            SDCPFlag.REPLY | SDCPFlag.ERROR,
            transaction_id,
            error_code.to_bytes(error_code_size, "big"),
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
        cls._validate_uint("index", index, cls.TRANSACTION_ID_SIZE)
        cls._validate_uint("subindex", subindex, cls.OPCODE_SIZE)
        address = index.to_bytes(cls.TRANSACTION_ID_SIZE, "big") + subindex.to_bytes(
            cls.OPCODE_SIZE, "big"
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
            ValueError: If a header field does not fit its protocol-defined size.

        """
        cls._validate_uint("opcode", opcode, cls.OPCODE_SIZE)
        cls._validate_uint("flags", flags, cls.FLAGS_SIZE)
        cls._validate_uint("transaction_id", transaction_id, cls.TRANSACTION_ID_SIZE)
        return b"".join((
            opcode.to_bytes(cls.OPCODE_SIZE, "big"),
            flags.to_bytes(cls.FLAGS_SIZE, "big"),
            transaction_id.to_bytes(cls.TRANSACTION_ID_SIZE, "big"),
            payload,
        ))

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
        transaction_id = int.from_bytes(frame[2 : cls.HEADER_SIZE], "big")
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

        if operation == SDCPOpcode.IDENTIFY:
            cls._validate_payload_size(payload, 0, "Identify request")
            return SDCPIdentifyRequest(transaction_id)
        if operation == SDCPOpcode.READ:
            index, subindex = cls._deserialize_dictionary_address(payload, "Read request", 0)
            return SDCPReadRequest(transaction_id, index, subindex)
        if operation == SDCPOpcode.WRITE:
            index, subindex = cls._deserialize_dictionary_address(payload, "Write request", 1)
            return SDCPWriteRequest(transaction_id, index, subindex, payload[3:])
        if operation == SDCPOpcode.SUBSCRIBE:
            return cls._deserialize_subscription_request(transaction_id, payload)
        if operation == SDCPOpcode.UNSUBSCRIBE:
            cls._validate_payload_size(payload, cls.TRANSACTION_ID_SIZE, "Unsubscribe request")
            return SDCPUnsubscribeRequest(transaction_id, int.from_bytes(payload, "big"))

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

        if operation == SDCPOpcode.IDENTIFY:
            return SDCPIdentifyResponse(transaction_id, payload)
        if operation == SDCPOpcode.READ:
            return SDCPReadResponse(transaction_id, payload)
        if operation == SDCPOpcode.WRITE:
            cls._validate_payload_size(payload, 0, "Write response")
            return SDCPWriteResponse(transaction_id)
        if operation == SDCPOpcode.SUBSCRIBE:
            cls._validate_payload_size(payload, cls.TRANSACTION_ID_SIZE, "Subscribe response")
            return SDCPSubscribeResponse(transaction_id, int.from_bytes(payload, "big"))
        if operation == SDCPOpcode.UNSUBSCRIBE:
            cls._validate_payload_size(payload, 0, "Unsubscribe response")
            return SDCPUnsubscribeResponse(transaction_id)

        return SDCPUnknownFrame(opcode, SDCPFlag.REPLY, transaction_id, payload)

    @classmethod
    def _deserialize_error_response(
        cls, opcode: int, transaction_id: int, payload: bytes
    ) -> SDCPErrorResponse:
        """Deserialize an SDCP error response.

        Returns:
            The specialized error response.

        Raises:
            ValueError: If the error payload is not a 32-bit error code.

        """
        error_code_size = 4
        cls._validate_payload_size(payload, error_code_size, "Error response")
        return SDCPErrorResponse(opcode, transaction_id, int.from_bytes(payload, "big"))

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
                int.from_bytes(payload[4:6], "big"),
                int.from_bytes(payload[6:8], "big"),
            )

        cls._validate_payload_size(payload, 6, "Event Subscribe request")
        return SDCPEventSubscriptionRequest(
            transaction_id,
            index,
            subindex,
            int.from_bytes(payload[4:6], "big"),
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
        minimum_size = cls.TRANSACTION_ID_SIZE + cls.OPCODE_SIZE + trailing_payload_size
        if len(payload) < minimum_size:
            raise ValueError(f"{message_name} payload is incomplete")
        return int.from_bytes(payload[:2], "big"), payload[2]

    @staticmethod
    def _validate_payload_size(payload: bytes, expected_size: int, message_name: str) -> None:
        """Validate the exact payload size of a fixed-layout message.

        Raises:
            ValueError: If the payload size does not match the message layout.

        """
        if len(payload) != expected_size:
            raise ValueError(f"{message_name} payload must contain {expected_size} bytes")

    @staticmethod
    def _validate_uint(field_name: str, value: int, size: int) -> None:
        """Validate that an integer fits in an unsigned protocol field.

        Raises:
            ValueError: If the integer cannot fit in the field.

        """
        maximum_value = (1 << (size * 8)) - 1
        if not 0 <= value <= maximum_value:
            raise ValueError(f"{field_name} must be in the range 0 to {maximum_value}")
