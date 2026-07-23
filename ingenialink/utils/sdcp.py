"""Serialization utilities for Servo Drives Control Protocol frames."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, IntFlag


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


@dataclass(frozen=True)
class SDCPFrame:
    """An SDCP acyclic frame split into its header and payload fields.

    Attributes:
        opcode: Operation identifier.
        flags: Bitmask that modifies the operation behavior.
        transaction_id: Request identifier echoed by the response.
        payload: Operation-specific bytes excluding a parsed dictionary address.
        index: Dictionary index parsed from a dictionary request, when available.
        subindex: Dictionary subindex parsed from a dictionary request, when available.

    """

    opcode: int
    flags: int
    transaction_id: int
    payload: bytes
    index: int | None = None
    subindex: int | None = None

    def __repr__(self) -> str:
        """Return a protocol-oriented representation of the SDCP frame."""
        dictionary_address = ""
        if self.index is not None and self.subindex is not None:
            dictionary_address = f", index=0x{self.index:04X}, subindex=0x{self.subindex:02X}"

        return (
            "SDCPFrame("
            f"opcode={self._format_opcode()}, flags={self._format_flags()}, "
            f"transaction_id=0x{self.transaction_id:04X}{dictionary_address}, "
            f"payload=0x{self.payload.hex().upper()})"
        )

    def _format_opcode(self) -> str:
        """Format the opcode as its name when it is defined by SDCP.

        Returns:
            The opcode name or its hexadecimal value when unknown.

        """
        try:
            return SDCPOpcode(self.opcode).name
        except ValueError:
            return f"0x{self.opcode:02X}"

    def _format_flags(self) -> str:
        """Format each known flag and retain unknown flag bits in hexadecimal.

        Returns:
            A pipe-delimited representation of the flag bits.

        """
        if self.flags == SDCPFlag.NONE:
            return SDCPFlag.NONE.name or "NONE"

        flag_names = [flag.name or f"0x{flag:02X}" for flag in SDCPFlag if self.flags & flag]
        known_flags = SDCPFlag.REPLY | SDCPFlag.ERROR
        unknown_flags = self.flags & ~known_flags
        if unknown_flags:
            flag_names.append(f"0x{unknown_flags:02X}")
        return " | ".join(flag_names) if flag_names else "0"


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
    def serialize(cls, opcode: int, flags: int, transaction_id: int, payload: bytes = b"") -> bytes:
        """Serialize an SDCP acyclic frame.

        Args:
            opcode: Operation identifier in the range 0 to 255.
            flags: Flag bitmask in the range 0 to 255.
            transaction_id: Request identifier in the range 0 to 65535.
            payload: Raw operation-specific bytes to append after the header.

        Returns:
            The big-endian SDCP frame ready to send as a UDP payload.

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
    def deserialize(cls, frame: bytes) -> SDCPFrame:
        """Deserialize an SDCP acyclic frame.

        Args:
            frame: The UDP payload containing an SDCP acyclic frame.

        Returns:
            The decoded SDCP frame.

        Raises:
            ValueError: If the frame is shorter than the four-byte SDCP header.

        """
        if len(frame) < cls.HEADER_SIZE:
            raise ValueError("SDCP frame must include a four-byte header")

        opcode = frame[0]
        flags = frame[1]
        payload = frame[cls.HEADER_SIZE :]
        index, subindex = cls._deserialize_dictionary_address(opcode, flags, payload)
        if index is not None and subindex is not None:
            payload = payload[3:]

        return SDCPFrame(
            opcode=opcode,
            flags=flags,
            transaction_id=int.from_bytes(frame[2 : cls.HEADER_SIZE], "big"),
            payload=payload,
            index=index,
            subindex=subindex,
        )

    @staticmethod
    def _deserialize_dictionary_address(
        opcode: int, flags: int, payload: bytes
    ) -> tuple[int | None, int | None]:
        """Deserialize a dictionary address from a dictionary request payload.

        Returns:
            The parsed index and subindex, or ``None`` values when absent.

        """
        dictionary_opcodes = (SDCPOpcode.READ, SDCPOpcode.WRITE, SDCPOpcode.SUBSCRIBE)
        if opcode not in dictionary_opcodes or flags != SDCPFlag.NONE or len(payload) < 3:
            return None, None

        return int.from_bytes(payload[:2], "big"), payload[2]

    @staticmethod
    def _validate_uint(field_name: str, value: int, size: int) -> None:
        """Validate that an integer fits in an unsigned protocol field.

        Raises:
            ValueError: If the integer cannot fit in the field.

        """
        maximum_value = (1 << (size * 8)) - 1
        if not 0 <= value <= maximum_value:
            raise ValueError(f"{field_name} must be in the range 0 to {maximum_value}")
