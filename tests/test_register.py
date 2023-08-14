import pytest

from ingenialink.register import Register
from ingenialink.register import REG_DTYPE, REG_ACCESS, REG_PHY, dtypes_ranges
from ingenialink.exceptions import ILValueError, ILAccessError
from ingenialink.ethernet.register import EthernetRegister
from ingenialink.canopen.register import CanopenRegister


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
        "enums": {"0": "TRIGGER_EVENT_AUTO", "1": "TRIGGER_EVENT_FORCED"},
        "cat_id": "MONITORING",
        "scat_id": "SUB_CATEGORY_TEST",
        "internal_use": "No description (invent here)",
    }
    aux_enums = []
    for key, value in reg_kwargs["enums"].items():
        test_dictionary = {"label": value, "value": int(key)}
        aux_enums.append(test_dictionary)

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
    assert register.enums == aux_enums
    assert register.enums_count == 2
    assert register.storage_valid == True


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
    assert type(register.storage) is float

    # parse int storage
    dtype = REG_DTYPE.U8
    storage = 123.1
    register = Register(dtype, access, storage=storage)
    assert type(register.storage) is int
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


@pytest.mark.no_connection
def test_register_range():
    access = REG_ACCESS.RW

    # custom range
    dtype = REG_DTYPE.U8
    range = (0, 100)
    register = Register(dtype, access, reg_range=range)
    assert type(register.range[0]) is int
    assert type(register.range[1]) is int
    assert register.range == range

    # custom range float
    dtype = REG_DTYPE.FLOAT
    range = (1.11, 100.25)
    register = Register(dtype, access, reg_range=range)
    assert type(register.range[0]) is float
    assert type(register.range[1]) is float
    assert register.range == range

    # default range
    dtype = REG_DTYPE.U8
    register = Register(dtype, access)
    assert register.range == (dtypes_ranges[dtype]["min"], dtypes_ranges[dtype]["max"])


@pytest.mark.no_connection
@pytest.mark.parametrize(
    "subnode, address, mapped_address_eth, mapped_address_can",
    [
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
