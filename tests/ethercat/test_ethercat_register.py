import pytest

from ingenialink.ethercat.register import EthercatRegister
from ingenialink.register import RegAccess, RegAddressType, RegDtype, RegPhy


@pytest.mark.no_connection
def test_getters_ethercat_register():
    reg_idx = 0x58F0
    reg_subidx = 0x00
    reg_dtype = RegDtype.U32
    reg_access = RegAccess.RW
    reg_kwargs = {
        "identifier": "MON_CFG_SOC_TYPE",
        "units": "none",
        "cyclic": "CONFIG",
        "phy": RegPhy.NONE,
        "subnode": 0,
        "storage": 1,
        "reg_range": (-20, 20),
        "labels": "Monitoring trigger type",
        "enums": {"TRIGGER_EVENT_AUTO": 0, "TRIGGER_EVENT_FORCED": 1},  # FIXME: INGK-1022
        "cat_id": "MONITORING",
        "scat_id": "SUB_CATEGORY_TEST",
        "internal_use": "No description (invent here)",
        "address_type": RegAddressType.NVM,
    }

    register = EthercatRegister(
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
