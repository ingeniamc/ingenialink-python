import pytest
from virtual_drive import resources as virtual_drive_resources

from ingenialink.ethernet.register import EthernetRegister
from ingenialink.exceptions import ILAccessError, ILValueError
from ingenialink.register import RegAccess, RegDtype, Register, RegPhy


@pytest.fixture
def connect_virtual_drive_with_bool_register(virtual_drive_custom_dict):
    def connect(dictionary):
        server, net, servo = virtual_drive_custom_dict(dictionary)

        boolean_reg_uid = "TEST_BOOLEAN"
        bool_register = EthernetRegister(
            0x0200, RegDtype.BOOL, RegAccess.RW, identifier=boolean_reg_uid
        )
        server._VirtualDrive__dictionary._add_register_list(bool_register)
        server._VirtualDrive__dictionary.registers(bool_register.subnode)[
            boolean_reg_uid
        ].storage_valid = True
        server._VirtualDrive__reg_address_to_id[bool_register.subnode][bool_register.address] = (
            boolean_reg_uid
        )
        server.reg_signals[boolean_reg_uid] = []
        servo.dictionary.registers(1)[boolean_reg_uid] = bool_register

        return servo, net

    return connect


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
def test_bit_register(connect_virtual_drive_with_bool_register, write_value, expected_read_value):
    dictionary = virtual_drive_resources.VIRTUAL_DRIVE_V2_XDF
    boolean_reg_uid = "TEST_BOOLEAN"
    servo, _ = connect_virtual_drive_with_bool_register(dictionary)

    servo.write(boolean_reg_uid, write_value)
    assert expected_read_value == servo.read(boolean_reg_uid)


@pytest.mark.parametrize(
    "write_value",
    [2, "one"],
)
def test_bit_register_write_invalid_value(connect_virtual_drive_with_bool_register, write_value):
    dictionary = virtual_drive_resources.VIRTUAL_DRIVE_V2_XDF
    servo, _ = connect_virtual_drive_with_bool_register(dictionary)
    with pytest.raises(ValueError) as exc_info:
        servo.write("TEST_BOOLEAN", write_value)
    assert (
        str(exc_info.value)
        == f"Invalid value. Expected values: [0, 1, True, False], got {write_value}"
    )


@pytest.mark.parametrize(
    "dtype, expected_bit_length",
    [
        (RegDtype.U8, 8),
        (RegDtype.S8, 8),
        (RegDtype.U16, 16),
        (RegDtype.S16, 16),
        (RegDtype.U32, 32),
        (RegDtype.S32, 32),
        (RegDtype.U64, 64),
        (RegDtype.S64, 64),
        (RegDtype.FLOAT, 32),
        (RegDtype.BOOL, 1),
        (RegDtype.BYTE_ARRAY_512, 512 * 8),
    ],
)
def test_bit_length_for_numeric_types(dtype, expected_bit_length):
    """Test that bit_length returns correct values for all numeric and fixed-size types."""
    register = Register(dtype, RegAccess.RW, identifier=f"TEST_{dtype.name}")
    assert register.bit_length == expected_bit_length


def test_bit_length_for_str_with_default():
    """Test that bit_length works for STR type when default value is provided."""
    # Default value is "2.8.0" encoded as hex: 322e382e30
    default_value = b"2.8.0"
    register = Register(
        RegDtype.STR,
        RegAccess.RO,
        identifier="TEST_STR",
        default=default_value,
    )
    assert register.bit_length == len(default_value) * 8
    assert register.bit_length == 40  # 5 bytes * 8


def test_bit_length_for_str_with_longer_default():
    """Test that bit_length works for STR type with a longer default value."""
    # Default value is "1.0.0.000" encoded
    default_value = b"1.0.0.000"
    register = Register(
        RegDtype.STR,
        RegAccess.RO,
        identifier="TEST_STR_LONG",
        default=default_value,
    )
    assert register.bit_length == len(default_value) * 8
    assert register.bit_length == 72  # 9 bytes * 8


def test_bit_length_for_str_without_default_raises_error():
    """Test that bit_length raises ValueError for STR type without default value."""
    register = Register(
        RegDtype.STR,
        RegAccess.RO,
        identifier="TEST_STR_NO_DEFAULT",
    )
    with pytest.raises(ValueError) as exc_info:
        _ = register.bit_length
    assert "Cannot determine bit_length for STR register 'TEST_STR_NO_DEFAULT'" in str(
        exc_info.value
    )
    assert "without a default value" in str(exc_info.value)
