import pytest

from ingenialink.ethernet.register import REG_DTYPE
from ingenialink.utils._utils import convert_dtype_to_bytes, convert_bytes_to_dtype
from ingenialink.utils.mcb import MCB
from ingenialink.constants import MCB_CMD_READ, MCB_CMD_WRITE
from ingenialink.exceptions import ILWrongCRCError, ILNACKError, ILWrongRegisterError


@pytest.mark.parametrize(
    "cmd, subnode, address, data, reg_dtype, extended, result",
    [
        (
            MCB_CMD_READ,
            1,
            0x630,
            None,
            REG_DTYPE.FLOAT,
            False,
            "a100026300000000000000009fcc",
        ),
        (
            MCB_CMD_WRITE,
            1,
            0x630,
            25.5,
            REG_DTYPE.FLOAT,
            False,
            "a10004630000cc4100000000cab1",
        ),
        (
            MCB_CMD_WRITE,
            1,
            0x6E5,
            "http://www.ingeniamc.com",
            REG_DTYPE.STR,
            True,
            "a100556e1800000000000000b44b687474703a2f2f7777772e696e67656e69616d632e636f6d",
        ),
    ],
)
def test_build_mcb_frame(cmd, subnode, address, data, reg_dtype, extended, result):
    default_frame_len = MCB.MCB_FRAME_SIZE
    if data is not None:
        data = convert_dtype_to_bytes(data, reg_dtype)
    frame = MCB.build_mcb_frame(cmd, subnode, address, data)
    if extended:
        assert len(frame) > default_frame_len
    else:
        assert len(frame) == default_frame_len
    assert result == frame.hex()


@pytest.mark.parametrize(
    "expected_address, data, reg_dtype, frame",
    [
        (
            0x6E5,
            "http://www.ingeniamc.com",
            REG_DTYPE.STR,
            "a100576e18000000000000003e9568"
            "7474703a2f2f7777772e696e67656e6"
            "9616d632e636f6d",
        )
    ],
)
def test_read_mcb_frame(expected_address, data, reg_dtype, frame):
    frame_byte_arr = bytearray.fromhex(frame)
    data_bytes = MCB.read_mcb_data(expected_address, frame_byte_arr)
    assert data == convert_bytes_to_dtype(data_bytes, reg_dtype)


@pytest.mark.parametrize(
    "expected_address, frame", [(0x630, "a10006630000704200000000dd71")]
)
def test_read_mcb_frame_wrong_crc(expected_address, frame):
    # replace CRC code with zeros
    frame = f"{frame[-4:]}0000"
    frame_byte_arr = bytearray.fromhex(frame)
    with pytest.raises(ILWrongCRCError):
        MCB.read_mcb_data(expected_address, frame_byte_arr)


@pytest.mark.parametrize(
    "expected_address, frame", [(0x11, "a1001c0100000106000000009ad7")]
)
def test_read_mcb_frame_nack(expected_address, frame):
    frame_byte_arr = bytearray.fromhex(frame)
    with pytest.raises(ILNACKError):
        MCB.read_mcb_data(expected_address, frame_byte_arr)


@pytest.mark.parametrize(
    "expected_address, frame", [(0x630, "a10006630000704200000000dd71")]
)
def test_read_mcb_frame_wrong_address(expected_address, frame):
    # Change expected address
    expected_address += 1
    frame_byte_arr = bytearray.fromhex(frame)
    with pytest.raises(ILWrongRegisterError):
        MCB.read_mcb_data(expected_address, frame_byte_arr)
