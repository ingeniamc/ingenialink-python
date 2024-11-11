import pytest

from ingenialink.bitfield import BitField
from tests.virtual.test_virtual_network import (
    connect_virtual_drive,  # noqa: F401
)

BITFIELD_EXAMPLES = {
    "BIT_0": BitField.bit(0),
    "BIT_1": BitField.bit(1),
    "BITS_2_3": BitField(start=2, end=3),
    "BIT_6": BitField.bit(6),
}


@pytest.mark.no_connection
@pytest.mark.parametrize(
    "value, values",
    [
        (0b1111_1111, {"BIT_0": 1, "BIT_1": 1, "BITS_2_3": 0b11, "BIT_6": 1}),
        (0b0000_0000, {"BIT_0": 0, "BIT_1": 0, "BITS_2_3": 0, "BIT_6": 0}),
        (0b0010_1010, {"BIT_0": 0, "BIT_1": 1, "BITS_2_3": 0b10, "BIT_6": 0}),
        (0b1110_1101, {"BIT_0": 1, "BIT_1": 0, "BITS_2_3": 0b11, "BIT_6": 1}),
    ],
)
def test_parse_bitfields(value, values):
    assert BitField.parse_bitfields(BITFIELD_EXAMPLES, value) == values


@pytest.mark.parametrize(
    "old_value, new_value, values",
    [
        (0b1101, 0b1111, {"BIT_1": 1}),  # Set bit
        (0b1111, 0b1111, {"BIT_1": 1}),  # Set already set bit
        (0b1111, 0b1101, {"BIT_1": 0}),  # Clear bit
        (0b1101, 0b1101, {"BIT_1": 0}),  # Clear already cleared bit
        (0b1111_0000, 0b1111_1100, {"BITS_2_3": 0b11}),  # Set multiple bits
        (0b1111_1100, 0b1111_0000, {"BITS_2_3": 0b00}),  # Clear multiple bits
        (0b1111_0100, 0b1111_1000, {"BITS_2_3": 0b10}),  # Set/Clear multiple bits
        (0b1010_1001, 0b1110_1100, {"BIT_0": 0, "BITS_2_3": 0b11, "BIT_6": 1}),
    ],
)
def test_set_bitfields(old_value, new_value, values):
    assert BitField.set_bitfields(BITFIELD_EXAMPLES, values, old_value) == new_value


@pytest.mark.parametrize(
    "values, error",
    [
        ({"BIT_0": 0b10}, "value 2 cannot be set to bitfield BIT_0. Max: 1"),
        ({"BITS_2_3": 0b100}, "value 4 cannot be set to bitfield BITS_2_3. Max: 3"),
    ],
)
def test_set_bitfield_over_max_value(values, error):
    with pytest.raises(ValueError) as ex:
        BitField.set_bitfields(BITFIELD_EXAMPLES, values, 0)

    assert ex.value.args[0] == error
