import pytest

from ingenialink.enums.register import RegDtype
from ingenialink.exceptions import ILValueError
from ingenialink.utils._utils import convert_bytes_to_dtype, convert_dtype_to_bytes


@pytest.mark.no_connection
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
def test_bytes_dtype_conversions(byts, value, dtype):
    assert convert_bytes_to_dtype(byts, dtype) == value

    assert convert_dtype_to_bytes(value, dtype) == byts


@pytest.mark.no_connection
def test_null_terminated_string():
    assert (
        convert_bytes_to_dtype(
            b"\x74\x68\x61\x74\x27\x73\x20\x67\x6f\x6f\x64\x00\xca\xca", RegDtype.STR
        )
        == "that's good"
    )


@pytest.mark.no_connection
def test_convert_bytes_to_dtype_wrong_string():
    wrong_data = b"\xff\xff\xff\xff\xff\x00"
    with pytest.raises(ILValueError):
        convert_bytes_to_dtype(wrong_data, RegDtype.STR)
