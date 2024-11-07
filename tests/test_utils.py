import pytest

from ingenialink.enums.register import REG_DTYPE
from ingenialink.exceptions import ILValueError
from ingenialink.utils._utils import convert_bytes_to_dtype


@pytest.mark.no_connection
@pytest.mark.parametrize(
    "v_input, v_output, dtype",
    [
        (b"\x00", 0, REG_DTYPE.S32),
        (b"\x00\x00\x0a\x42", 34.5, REG_DTYPE.FLOAT),
        (b"\xFF", 255, REG_DTYPE.U16),
        (b"\x74\x68\x61\x74\x27\x73\x20\x61\x20\x74\x65\x73\x74", "that's a test", REG_DTYPE.STR),
        (b"\x74\x68\x61\x74\x27\x73\x20\x67\x6f\x6f\x64\x00\xca\xca", "that's good", REG_DTYPE.STR),
    ],
)
def test_convert_bytes_to_dtype(v_input, v_output, dtype):
    assert convert_bytes_to_dtype(v_input, dtype) == v_output


@pytest.mark.no_connection
def test_convert_bytes_to_dtype_wrong_string():
    wrong_data = b"\xff\xff\xff\xff\xff\x00"
    with pytest.raises(ILValueError):
        convert_bytes_to_dtype(wrong_data, REG_DTYPE.STR)
