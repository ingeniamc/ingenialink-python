import copy
import pickle
import struct

import pytest
from ingenialink._rust import data_type as _rust_data_type

from ingenialink.enums.register import ByteOrder, RegDtype
from ingenialink.exceptions import ILValueError

RustDataType = _rust_data_type.DataType


def configured(
    dtype: RegDtype, byte_order: ByteOrder = ByteOrder.LITTLE
) -> _rust_data_type.ConfiguredDataType:
    """Resolve a configured native codec for test conversion calls.

    Returns:
        A native codec configured for the requested data type and byte order.
    """
    data_type = RustDataType.from_name(dtype.name)
    assert data_type is not None
    return data_type.with_byte_order(byte_order.value)


@pytest.mark.parametrize(
    "byts, value, dtype",
    [
        (b"\x03", 3, RegDtype.U8),
        (b"\x75\x00", 0x0075, RegDtype.U16),
        (b"\x35\x23", 0x2335, RegDtype.U16),
        (b"\x34\x12\x75\x45", 0x45751234, RegDtype.U32),
        (b"\xf2", -14, RegDtype.S8),
        (b"\x75\xf0", -3979, RegDtype.S16),
        (b"\x35\x23", 0x2335, RegDtype.S16),
        (b"\x34\x12\x75\x45", 0x45751234, RegDtype.S32),
        (b"\x00\x00\x0a\x42", 34.5, RegDtype.FLOAT),
        (b"\x74\x68\x61\x74\x27\x73\x20\x61\x20\x74\x65\x73\x74", "that's a test", RegDtype.STR),
        (bytes(512), bytes(512), RegDtype.BYTE_ARRAY_512),
    ],
)
def test_round_trip_matches_python_reference(byts, value, dtype):
    dt = configured(dtype)

    assert dt.bytes_to_value(byts) == value
    assert dt.value_to_bytes(value) == byts


def test_float_uses_big_endian_byte_order():
    data = b"\x42\x0a\x00\x00"
    value = 34.5
    dt = configured(RegDtype.FLOAT, ByteOrder.BIG)

    assert dt.bytes_to_value(data) == pytest.approx(value)
    assert dt.value_to_bytes(value) == data


def test_configured_data_type_uses_fixed_byte_order():
    dt = RustDataType.U16.with_byte_order(ByteOrder.BIG.value)

    assert dt.bytes_to_value(b"\x12\x34") == 0x1234
    assert dt.value_to_bytes(0x1234) == b"\x12\x34"


def test_configured_data_type_does_not_support_copying():
    """Verify native codecs remain unsupported by Python copy and pickle protocols."""
    dt = RustDataType.U16.with_byte_order(ByteOrder.BIG.value)

    with pytest.raises(TypeError):
        copy.deepcopy(dt)
    with pytest.raises(TypeError):
        pickle.dumps(dt)


def test_byte_array_preserves_python_bytes_identity():
    payload = bytes(range(256)) * 2
    dt = RustDataType.ByteArray512.with_byte_order(ByteOrder.LITTLE.value)

    assert dt.bytes_to_value(payload) is payload
    assert dt.value_to_bytes(payload) is payload


def test_byte_array_requires_exactly_512_bytes():
    dt = RustDataType.ByteArray512.with_byte_order(ByteOrder.LITTLE.value)

    with pytest.raises(struct.error):
        dt.bytes_to_value(b"payload")
    with pytest.raises(struct.error):
        dt.value_to_bytes(b"payload")


def test_null_terminated_string():
    dt = configured(RegDtype.STR)
    assert dt.bytes_to_value(b"\x74\x68\x61\x74\x27\x73\x20\x67\x6f\x6f\x64\x00\xca\xca") == (
        "that's good"
    )


def test_invalid_utf8_string_raises_ilvalueerror():
    dt = configured(RegDtype.STR)
    with pytest.raises(ILValueError):
        dt.bytes_to_value(b"\xff\xff\xff\xff\xff\x00")


@pytest.mark.parametrize(
    "dtype, byte_length, bit_length, signed",
    [
        (RegDtype.U8, 1, 8, False),
        (RegDtype.S8, 1, 8, True),
        (RegDtype.U16, 2, 16, False),
        (RegDtype.S16, 2, 16, True),
        (RegDtype.U32, 4, 32, False),
        (RegDtype.S32, 4, 32, True),
        (RegDtype.U64, 8, 64, False),
        (RegDtype.S64, 8, 64, True),
        (RegDtype.FLOAT, 4, 32, False),
        (RegDtype.BOOL, 1, 8, False),
        (RegDtype.STR, None, None, False),
        (RegDtype.BYTE_ARRAY_512, 512, 4096, False),
    ],
)
def test_dtype_metadata(dtype, byte_length, bit_length, signed):
    dt = RustDataType.from_name(dtype.name)
    assert dt.byte_length() == byte_length
    assert dt.bit_length() == bit_length
    assert dt.is_signed() == signed


@pytest.mark.parametrize("dtype", list(RegDtype))
def test_dtype_name_matches_regdtype(dtype):
    dt = RustDataType.from_name(dtype.name)
    assert dt is not None


def test_dtype_equality():
    assert RustDataType.from_name(RegDtype.U8.name) == RustDataType.U8
    assert RustDataType.U8 != RustDataType.U16


def test_from_name_unknown_returns_none():
    assert RustDataType.from_name("UNKNOWN") is None


@pytest.mark.parametrize("dtype, payload", [(RegDtype.U16, b"\xff"), (RegDtype.S16, b"\xff")])
def test_short_integer_payload_raises_struct_error(dtype, payload):
    with pytest.raises(struct.error):
        configured(dtype).bytes_to_value(payload)


def test_long_integer_payload_raises_struct_error():
    with pytest.raises(struct.error):
        configured(RegDtype.U16).bytes_to_value(b"\x01\x02\x03")


def test_short_float_payload_raises_struct_error():
    with pytest.raises(struct.error):
        configured(RegDtype.FLOAT).bytes_to_value(b"\x01")


def test_out_of_range_raises_overflow_error():
    with pytest.raises(OverflowError):
        configured(RegDtype.U8).value_to_bytes(256)


def test_wrong_value_type_raises_value_error():
    with pytest.raises(ValueError):
        configured(RegDtype.U8).value_to_bytes("hello")


def test_bool_accepts_only_0_1_and_bools():
    codec = configured(RegDtype.BOOL)
    assert codec.value_to_bytes(True) == b"\x01"
    assert codec.value_to_bytes(1) == b"\x01"
    assert codec.value_to_bytes(False) == b"\x00"
    with pytest.raises(ValueError):
        codec.value_to_bytes(2)


def test_unsupported_byte_order_raises_value_error():
    with pytest.raises(ValueError):
        RustDataType.U8.with_byte_order("bad")
