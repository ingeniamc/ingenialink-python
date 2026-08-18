import pytest

from ingenialink.enums.register import ByteOrder
from ingenialink.exceptions import ILAccessError, ILValueError
from ingenialink.register import RegAccess, RegDtype, Register, RegPhy
from ingenialink.servo import Servo


class BigEndianServo(Servo):
    """Minimal servo exposing the protocol byte order used by TSN servos."""

    _REGISTER_BYTE_ORDER = ByteOrder.BIG

    def _get_reg(self, reg, _subnode):
        """Return the supplied register without dictionary lookup."""
        return reg

    def _read_raw(self, _reg):
        """Return the configured raw payload."""
        return self.raw_data

    def _write_raw(self, _reg, data):
        """Store the raw payload written by the codec."""
        self.raw_data = data

    def _notify_register_update(self, reg, data):
        """Suppress observer handling in this codec-focused test double."""


def test_getters_register():
    reg_dtype = RegDtype.U32
    reg_access = RegAccess.RW
    reg_kwargs = {
        "identifier": "MON_CFG_SOC_TYPE",
        "units": None,
        "pdo_access": "CONFIG",
        "phy": RegPhy.NONE,
        "subnode": 0,
        "storage": 1,
        "reg_range": (-20, 20),
        "labels": "Monitoring trigger type",
        "enums": {"TRIGGER_EVENT_AUTO": 0, "TRIGGER_EVENT_FORCED": 1},
        "cat_id": "MONITORING",
        "scat_id": "SUB_CATEGORY_TEST",
        "internal_use": 1,
    }
    register = Register(reg_dtype, reg_access, **reg_kwargs)

    assert register.identifier == reg_kwargs["identifier"]
    assert register.units == reg_kwargs["units"]
    assert register.pdo_access == reg_kwargs["pdo_access"]
    assert register.dtype == reg_dtype
    assert register.access == reg_access
    assert register.phy == reg_kwargs["phy"]
    assert register.subnode == reg_kwargs["subnode"]
    assert register.storage == reg_kwargs["storage"]
    assert register.range == reg_kwargs["reg_range"]
    assert register.labels == reg_kwargs["labels"]
    assert register.cat_id == reg_kwargs["cat_id"]
    assert register.scat_id == reg_kwargs["scat_id"]
    assert register.internal_use == reg_kwargs["internal_use"]
    assert register.enums == reg_kwargs["enums"]
    assert register.enums_count == 2
    assert register.storage_valid


def test_register_type_errors():
    dtype = "False type"
    access = RegAccess.RW
    with pytest.raises(ILValueError):
        Register(dtype, access, "MOCK")

    dtype = RegDtype.FLOAT
    access = "False access"
    with pytest.raises(ILAccessError):
        Register(dtype, access, "MOCK")

    dtype = RegDtype.FLOAT
    access = RegAccess.RW
    with pytest.raises(ILValueError):
        Register(dtype, access, phy="False Phy", identifier="MOCK")


def test_register_get_storage():
    access = RegAccess.RW

    # invalid storage
    dtype = RegDtype.STR
    register = Register(dtype, access, storage=1, identifier="MOCK")
    assert register.storage_valid == 0
    assert register.storage is None

    # no storage
    dtype = RegDtype.FLOAT
    register = Register(dtype, access, identifier="MOCK")
    assert register.storage_valid == 0
    assert register.storage is None

    # float storage
    dtype = RegDtype.FLOAT
    storage = 12.34
    register = Register(dtype, access, storage=storage, identifier="MOCK")
    assert register.storage_valid == 1
    assert register.storage == storage

    # parse float storage
    dtype = RegDtype.FLOAT
    storage = 123
    register = Register(dtype, access, storage=storage, identifier="MOCK")
    assert isinstance(register.storage, float)

    # parse int storage
    dtype = RegDtype.U8
    storage = 123.1
    register = Register(dtype, access, storage=storage, identifier="MOCK")
    assert isinstance(register.storage, int)
    assert register.storage == 123


def test_register_set_storage():
    access = RegAccess.RW
    dtype = RegDtype.FLOAT
    storage = 20.0
    register = Register(dtype, access, storage=storage, identifier="MOCK")
    assert register.storage == storage
    storage = 1.1
    register.storage = storage
    assert register.storage == storage


@pytest.mark.parametrize(
    "dtype, value, expected",
    [
        (RegDtype.U32, 0x12345678, b"\x78\x56\x34\x12"),
        (RegDtype.FLOAT, 34.5, b"\x00\x00\x0a\x42"),
        (RegDtype.STR, "hello", b"hello"),
        (RegDtype.BYTE_ARRAY_512, bytes(512), bytes(512)),
    ],
)
def test_register_value_to_bytes(dtype, value, expected):
    register = Register(dtype, RegAccess.RW, identifier="MOCK")

    assert register.value_to_bytes(value) == expected


def test_servo_uses_its_protocol_byte_order_for_register_conversion():
    servo = BigEndianServo.__new__(BigEndianServo)
    register = Register(RegDtype.U16, RegAccess.RW, identifier="MOCK")
    servo.raw_data = b"\x12\x34"

    assert servo.read(register) == 0x1234

    servo.write(register, 0x5678)

    assert servo.raw_data == b"\x56\x78"


def test_register_resolves_codecs_on_construction():
    register = Register(RegDtype.U16, RegAccess.RW, identifier="MOCK")

    little_codec = register._codec_little
    big_codec = register._codec_big

    assert register.get_codec(ByteOrder.LITTLE) is little_codec
    assert register.get_codec(ByteOrder.BIG) is big_codec
    assert little_codec is register._codec_little
    assert big_codec is register._codec_big
    assert little_codec.value_to_bytes(0x1234) == b"\x34\x12"
    assert big_codec.value_to_bytes(0x1234) == b"\x12\x34"


@pytest.mark.parametrize(
    "dtype, reg_range, expected_range, reg_type",
    [
        (RegDtype.BOOL, ("0", "1"), (0, 1), int),
        (RegDtype.U8, (0, 100), (0, 100), int),
        (RegDtype.FLOAT, (0.0, 1.0), (0.0, 1.0), float),
        (RegDtype.S16, (-100, None), (-100, 32767), int),
        (RegDtype.U32, (None, 100), (0, 100), int),
        (RegDtype.S32, (None, None), (-2147483648, 2147483647), int),
        (RegDtype.FLOAT, (None, None), (-3.4e38, 3.4e38), float),
    ],
)
def test_register_range(dtype, reg_range, expected_range, reg_type):
    register = Register(dtype, RegAccess.RW, reg_range=reg_range, identifier="MOCK")

    assert type(register.range[0]) is reg_type
    assert type(register.range[1]) is reg_type
    assert register.range == expected_range


@pytest.mark.parametrize(
    "write_value, expected_read_value,",
    [
        (0, False),
        (1, True),
        (False, False),
        (True, True),
    ],
)
def test_bit_register(virtual_drive, write_value, expected_read_value):
    boolean_reg_uid = "TEST_BOOLEAN"
    _, servo = virtual_drive

    servo.write(boolean_reg_uid, write_value)
    assert expected_read_value == servo.read(boolean_reg_uid)


@pytest.mark.parametrize(
    "write_value",
    [2, "one"],
)
def test_bit_register_write_invalid_value(virtual_drive, write_value):
    _, servo = virtual_drive
    with pytest.raises(ValueError) as exc_info:
        servo.write("TEST_BOOLEAN", write_value)
    assert (
        str(exc_info.value)
        == f"Invalid value. Expected values: [0, 1, True, False], got {write_value}"
    )


class TestRegisterEquality:
    def test_equal_registers(self):
        reg1 = Register(RegDtype.U32, RegAccess.RW, identifier="MOT_POLE_PAIRS", subnode=1)
        reg2 = Register(RegDtype.U32, RegAccess.RW, identifier="MOT_POLE_PAIRS", subnode=1)
        assert reg1 == reg2
        assert reg1 == reg2

    def test_different_identifier(self):
        reg1 = Register(RegDtype.U32, RegAccess.RW, identifier="MOT_POLE_PAIRS", subnode=1)
        reg2 = Register(RegDtype.U32, RegAccess.RW, identifier="DRV_OP_CMD", subnode=1)
        assert reg1 != reg2

    def test_different_subnode(self):
        reg1 = Register(RegDtype.U32, RegAccess.RW, identifier="MOT_POLE_PAIRS", subnode=0)
        reg2 = Register(RegDtype.U32, RegAccess.RW, identifier="MOT_POLE_PAIRS", subnode=1)
        assert reg1 != reg2

    def test_same_identity_ignores_other_fields(self):
        reg1 = Register(RegDtype.U32, RegAccess.RW, identifier="REG_A", subnode=1)
        reg2 = Register(RegDtype.FLOAT, RegAccess.RO, identifier="REG_A", subnode=1)
        assert reg1 == reg2

    def test_hash_consistent_with_equality(self):
        reg1 = Register(RegDtype.U32, RegAccess.RW, identifier="MOT_POLE_PAIRS", subnode=1)
        reg2 = Register(RegDtype.FLOAT, RegAccess.RO, identifier="MOT_POLE_PAIRS", subnode=1)
        assert hash(reg1) == hash(reg2)

    def test_usable_as_dict_key(self):
        reg1 = Register(RegDtype.U32, RegAccess.RW, identifier="MOT_POLE_PAIRS", subnode=1)
        reg2 = Register(RegDtype.U32, RegAccess.RW, identifier="MOT_POLE_PAIRS", subnode=1)
        d = {reg1: 42}
        assert d[reg2] == 42

    def test_not_equal_to_non_register(self):
        reg = Register(RegDtype.U32, RegAccess.RW, identifier="REG_A", subnode=1)
        assert reg != "REG_A"
        assert reg != 42
        assert reg != (1, "REG_A")
