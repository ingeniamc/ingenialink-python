from collections.abc import Iterable
from typing import Optional


def _bit_mask(selected_bits: Iterable[int]) -> int:
    """Bit mask creator.

    Creates an integer bit mask that masks a number of bits

    Args:
        selected_bits: Iterable of bits that are selected for the mask

    Returns:
        bit mask
    """
    return sum(1 << bit for bit in selected_bits)


class BitField:
    """Bit or group of bits that are part of a integer register.

    Args:
        start: First bit of the register that is part of the bitfield
        end: Last bit of the register that is part of the bitfield
    """

    def __init__(self, start: int, end: int):
        self._start = start
        self._end = end
        self._len = end - start + 1
        self._max_value = 2**self._len - 1
        self._mask = _bit_mask(range(start, end + 1))

    def __eq__(self, other: object) -> bool:
        """Compare bitfields.

        Args:
            other: object to compare it to.

        Returns:
            True if they are equal, False otherwise.
        """
        if not isinstance(other, BitField):
            return False
        return (self._start == other._start) and (self._end == other._end)

    @classmethod
    def bit(cls, bit: int) -> "BitField":
        """Bitfield of single bit.

        Returns:
            Bitfield.
        """
        return cls(start=bit, end=bit)

    @staticmethod
    def parse_bitfields(bitfields: dict[str, "BitField"], value: int) -> dict[str, int]:
        """Parse value into bitfields.

        Separates a integer value into a dictionary of values, where the key is the bitfield name

        Args:
            bitfields: Dictionary of bitfields.
                Key is the name of the bitfield.
                Value is the bitfield specification
            value: Integer value of the register

        Returns:
            Dictionary with values of the bitfields.
            Key is the name of the bitfield.
            Value is the value parsed.
        """
        return {
            name: (value & bitfield._mask) >> bitfield._start
            for name, bitfield in bitfields.items()
        }

    @staticmethod
    def set_bitfields(
        bitfields: dict[str, "BitField"], values: dict[str, int], value: Optional[int] = None
    ) -> int:
        """Set bitfields to a value.

        Args:
            bitfields: Dictionary of bitfields.
                Key is the name of the bitfield.
                Value is the bitfield specification
            values: Dictionary with values of the bitfields.
                Key is the name of the bitfield.
                Value is the value to set.
            value: Previous integer value of the register.
                If not provided, it defaults to 0.

        Raises:
            KeyError: If the bitfield name does not exist.
            ValueError: If one of the values to set does not fit in the bitfield space

        Returns:
            New integer value of the register with the bitfields set
        """
        if value is None:
            value = 0
        for name, new_bitfields_value in values.items():
            if name not in bitfields:
                raise KeyError(f"Bitfield {name} does not exist")
            bitfield = bitfields[name]

            if new_bitfields_value > bitfield._max_value:
                raise ValueError(
                    f"value {new_bitfields_value} cannot be set to bitfield {name}. "
                    f"Max: {bitfield._max_value}"
                )

            # Clear bits
            value &= ~bitfield._mask
            # Set new bits, shifting to position
            value |= bitfield._mask & (new_bitfields_value << bitfield._start)

        return value
