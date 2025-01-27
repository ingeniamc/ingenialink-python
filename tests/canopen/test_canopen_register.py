import pytest

from ingenialink.canopen.register import (
    REG_ADDRESS_TYPE,
    CanopenRegister,
    RegAccess,
    RegCyclicType,
    RegDtype,
    RegPhy,
)
from ingenialink.dictionary import Dictionary


@pytest.mark.no_connection
def test_getters_canopen_register():
    reg_idx = 0x58F0
    reg_subidx = 0x00
    reg_dtype = RegDtype.U32
    reg_access = RegAccess.RW
    reg_kwargs = {
        "identifier": "MON_CFG_SOC_TYPE",
        "units": "none",
        "cyclic": RegCyclicType.CONFIG,
        "phy": RegPhy.NONE,
        "subnode": 0,
        "storage": 1,
        "reg_range": (-20, 20),
        "labels": "Monitoring trigger type",
        "enums": {"TRIGGER_EVENT_AUTO": 0, "TRIGGER_EVENT_FORCED": 1},  # FIXME: INGK-1022
        "cat_id": "MONITORING",
        "scat_id": "SUB_CATEGORY_TEST",
        "internal_use": "No description (invent here)",
        "address_type": REG_ADDRESS_TYPE.NVM,
        "is_node_id_dependent": True,
    }

    register = CanopenRegister(
        reg_idx,
        reg_subidx,
        reg_dtype,
        reg_access,
        **reg_kwargs,
    )

    assert register.idx == reg_idx
    assert register.subidx == reg_subidx
    assert register.dtype == reg_dtype
    assert register.access == reg_access
    assert register.identifier == reg_kwargs["identifier"]
    assert register.units == reg_kwargs["units"]
    assert register.cyclic == reg_kwargs["cyclic"]
    assert register.phy == reg_kwargs["phy"]
    assert register.subnode == reg_kwargs["subnode"]
    assert register.storage == reg_kwargs["storage"]
    assert register.range == reg_kwargs["reg_range"]
    assert register.labels == reg_kwargs["labels"]
    assert register.cat_id == reg_kwargs["cat_id"]
    assert register.scat_id == reg_kwargs["scat_id"]
    assert register.internal_use == reg_kwargs["internal_use"]
    assert register.address_type == reg_kwargs["address_type"]
    assert register.enums == reg_kwargs["enums"]
    assert register.enums_count == 2
    assert register.storage_valid
    assert register.is_node_id_dependent is True


@pytest.mark.canopen
def test_canopen_connection_register(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    assert isinstance(servo.dictionary, Dictionary)

    registers_sub_0 = servo.dictionary.registers(0)
    assert registers_sub_0 is not None
    registers_sub_1 = servo.dictionary.registers(1)
    assert registers_sub_1 is not None

    register = registers_sub_1.get("DRV_OP_CMD")
    assert isinstance(register, CanopenRegister)

    assert register.identifier == "DRV_OP_CMD"
    assert register.units == "-"
    assert register.cyclic == RegCyclicType.RX
    assert register.dtype == RegDtype.U16
    assert register.access, RegAccess.RW
    assert register.idx == 0x2014
    assert register.subidx == 0
    assert register.phy == RegPhy.NONE
    assert register.subnode == 1
    assert register.storage is None
    assert not register.storage_valid
    assert register.range == (0, 65535)
    assert register.labels is not None
    assert len(register.enums) == 13
    assert register.enums_count == 13
    assert register.cat_id == "TARGET"
    assert register.scat_id is None
    assert register.internal_use == 0
    assert register.is_node_id_dependent is False
