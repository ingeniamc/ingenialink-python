import os

import pytest

from ingenialink.canopen.register import CanopenRegister
from ingenialink.ethernet.register import EthernetRegister
from ingenialink.exceptions import ILAccessError, ILValueError
from ingenialink.register import REG_ACCESS, REG_DTYPE, REG_PHY, Register
from ingenialink.virtual.network import VirtualNetwork
from virtual_drive.core import VirtualDrive

TEST_PORT = 82
server = VirtualDrive(TEST_PORT)


@pytest.fixture(scope="function")
def stop_virtual_drive():
    yield
    server.stop()


@pytest.fixture
def connect_virtual_drive_with_bool_register():
    def connect(dictionary):
        global server
        server.stop()
        server = VirtualDrive(TEST_PORT, dictionary)
        server.start()
        net = VirtualNetwork()
        servo = net.connect_to_slave(dictionary, TEST_PORT)

        boolean_reg_uid = "TEST_BOOLEAN"
        bool_register = EthernetRegister(
            0x0200, REG_DTYPE.BOOL, REG_ACCESS.RW, identifier=boolean_reg_uid
        )
        server._VirtualDrive__dictionary._add_register_list(bool_register)
        server._VirtualDrive__dictionary.registers(bool_register.subnode)[
            boolean_reg_uid
        ].storage_valid = True
        server._VirtualDrive__reg_address_to_id[bool_register.subnode][
            bool_register.address
        ] = boolean_reg_uid
        server.reg_signals[boolean_reg_uid] = []
        servo.dictionary.registers(1)[boolean_reg_uid] = bool_register

        return servo, net

    return connect


@pytest.mark.no_connection
def test_getters_register():
    reg_dtype = REG_DTYPE.U32
    reg_access = REG_ACCESS.RW
    reg_kwargs = {
        "identifier": "MON_CFG_SOC_TYPE",
        "units": "none",
        "cyclic": "CONFIG",
        "phy": REG_PHY.NONE,
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
    assert register.cyclic == reg_kwargs["cyclic"]
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


@pytest.mark.no_connection
def test_register_type_errors():
    dtype = "False type"
    access = REG_ACCESS.RW
    with pytest.raises(ILValueError):
        Register(dtype, access)

    dtype = REG_DTYPE.FLOAT
    access = "False access"
    with pytest.raises(ILAccessError):
        Register(dtype, access)

    dtype = REG_DTYPE.FLOAT
    access = REG_ACCESS.RW
    with pytest.raises(ILValueError):
        Register(dtype, access, phy="False Phy")


@pytest.mark.no_connection
def test_register_get_storage():
    access = REG_ACCESS.RW

    # invalid storage
    dtype = REG_DTYPE.STR
    register = Register(dtype, access, storage=1)
    assert register.storage_valid == 0
    assert register.storage is None

    # no storage
    dtype = REG_DTYPE.FLOAT
    register = Register(dtype, access)
    assert register.storage_valid == 0
    assert register.storage is None

    # float storage
    dtype = REG_DTYPE.FLOAT
    storage = 12.34
    register = Register(dtype, access, storage=storage)
    assert register.storage_valid == 1
    assert register.storage == storage

    # parse float storage
    dtype = REG_DTYPE.FLOAT
    storage = 123
    register = Register(dtype, access, storage=storage)
    assert isinstance(register.storage, float)

    # parse int storage
    dtype = REG_DTYPE.U8
    storage = 123.1
    register = Register(dtype, access, storage=storage)
    assert isinstance(register.storage, int)
    assert register.storage == 123


@pytest.mark.no_connection
def test_register_set_storage():
    access = REG_ACCESS.RW
    dtype = REG_DTYPE.FLOAT
    storage = 20.0
    register = Register(dtype, access, storage=storage)
    assert register.storage == storage

    storage = 1.1
    register.storage = storage
    assert register.storage == storage


@pytest.mark.parametrize(
    "dtype, reg_range, expected_range, reg_type",
    [
        (REG_DTYPE.U8, (0, 100), (0, 100), int),
        (REG_DTYPE.FLOAT, (0.0, 1.0), (0.0, 1.0), float),
        (REG_DTYPE.S16, (-100, None), (-100, 32767), int),
        (REG_DTYPE.U32, (None, 100), (0, 100), int),
        (REG_DTYPE.S32, (None, None), (-2147483648, 2147483647), int),
        (REG_DTYPE.FLOAT, (None, None), (-3.4e38, 3.4e38), float),
    ],
)
@pytest.mark.no_connection
def test_register_range(dtype, reg_range, expected_range, reg_type):
    register = Register(dtype, REG_ACCESS.RW, reg_range=reg_range)

    assert type(register.range[0]) is reg_type
    assert type(register.range[1]) is reg_type
    assert register.range == expected_range


@pytest.mark.no_connection
@pytest.mark.parametrize(
    "subnode, address, mapped_address_eth, mapped_address_can",
    [
        (0, 0x0000, 0x0000, 0x0000),
        (1, 0x0010, 0x0010, 0x0010),
        (2, 0x0020, 0x0820, 0x0020),
        (3, 0x0030, 0x1030, 0x0030),
    ],
)
def test_register_mapped_address(subnode, address, mapped_address_eth, mapped_address_can):
    ethernet_param_dict = {
        "subnode": subnode,
        "address": address,
        "dtype": REG_DTYPE.U16,
        "access": REG_ACCESS.RW,
    }
    canopen_param_dict = {
        "subnode": subnode,
        "idx": address,
        "subidx": 0x00,
        "dtype": REG_DTYPE.U16,
        "access": REG_ACCESS.RW,
        "identifier": "",
        "units": "",
        "cyclic": "CONFIG",
    }
    register = EthernetRegister(**ethernet_param_dict)
    assert mapped_address_eth == register.mapped_address
    register = CanopenRegister(**canopen_param_dict)
    assert mapped_address_can == register.mapped_address


@pytest.mark.parametrize(
    "write_value, expected_read_value,",
    [
        (0, False),
        (1, True),
        (False, False),
        (True, True),
    ],
)
@pytest.mark.usefixtures("stop_virtual_drive")
@pytest.mark.no_connection
def test_bit_register(connect_virtual_drive_with_bool_register, write_value, expected_read_value):
    dictionary = os.path.join("virtual_drive/resources/", "virtual_drive.xdf")
    boolean_reg_uid = "TEST_BOOLEAN"
    servo, _ = connect_virtual_drive_with_bool_register(dictionary)

    servo.write(boolean_reg_uid, write_value)
    assert expected_read_value == servo.read(boolean_reg_uid)


@pytest.mark.parametrize(
    "write_value",
    [2, "one"],
)
@pytest.mark.no_connection
@pytest.mark.usefixtures("stop_virtual_drive")
def test_bit_register_write_invalid_value(connect_virtual_drive_with_bool_register, write_value):
    dictionary = os.path.join("virtual_drive/resources/", "virtual_drive.xdf")
    servo, _ = connect_virtual_drive_with_bool_register(dictionary)
    with pytest.raises(ValueError) as exc_info:
        servo.write("TEST_BOOLEAN", write_value)
    assert (
        str(exc_info.value)
        == f"Invalid value. Expected values: [0, 1, True, False], got {write_value}"
    )
