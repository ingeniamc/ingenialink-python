import pytest

from ingenialink.exceptions import ILAccessError, ILValueError
from ingenialink.register import RegAccess, RegDtype, Register, RegPhy


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
        Register(dtype, access)

    dtype = RegDtype.FLOAT
    access = "False access"
    with pytest.raises(ILAccessError):
        Register(dtype, access)

    dtype = RegDtype.FLOAT
    access = RegAccess.RW
    with pytest.raises(ILValueError):
        Register(dtype, access, phy="False Phy")


def test_register_get_storage():
    access = RegAccess.RW

    # invalid storage
    dtype = RegDtype.STR
    register = Register(dtype, access, storage=1)
    assert register.storage_valid == 0
    assert register.storage is None

    # no storage
    dtype = RegDtype.FLOAT
    register = Register(dtype, access)
    assert register.storage_valid == 0
    assert register.storage is None

    # float storage
    dtype = RegDtype.FLOAT
    storage = 12.34
    register = Register(dtype, access, storage=storage)
    assert register.storage_valid == 1
    assert register.storage == storage

    # parse float storage
    dtype = RegDtype.FLOAT
    storage = 123
    register = Register(dtype, access, storage=storage)
    assert isinstance(register.storage, float)

    # parse int storage
    dtype = RegDtype.U8
    storage = 123.1
    register = Register(dtype, access, storage=storage)
    assert isinstance(register.storage, int)
    assert register.storage == 123


def test_register_set_storage():
    access = RegAccess.RW
    dtype = RegDtype.FLOAT
    storage = 20.0
    register = Register(dtype, access, storage=storage)
    assert register.storage == storage

    storage = 1.1
    register.storage = storage
    assert register.storage == storage


@pytest.mark.parametrize(
    "dtype, reg_range, expected_range, reg_type",
    [
        (RegDtype.U8, (0, 100), (0, 100), int),
        (RegDtype.FLOAT, (0.0, 1.0), (0.0, 1.0), float),
        (RegDtype.S16, (-100, None), (-100, 32767), int),
        (RegDtype.U32, (None, 100), (0, 100), int),
        (RegDtype.S32, (None, None), (-2147483648, 2147483647), int),
        (RegDtype.FLOAT, (None, None), (-3.4e38, 3.4e38), float),
    ],
)
def test_register_range(dtype, reg_range, expected_range, reg_type):
    register = Register(dtype, RegAccess.RW, reg_range=reg_range)

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
