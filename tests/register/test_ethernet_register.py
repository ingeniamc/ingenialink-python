import pytest

from ingenialink.ethernet.register import EthernetRegister
from ingenialink.register import REG_DTYPE, REG_ACCESS, REG_PHY, REG_ADDRESS_TYPE, dtypes_ranges
from ingenialink.utils._utils import exc


@pytest.mark.smoke
def test_getters_ethernet_register():
    test_cyclic = "CONFIG"
    test_addr = 0x58F0
    test_dtype = REG_DTYPE.U32
    test_access = REG_ACCESS.RW
    test_identification = "MON_CFG_SOC_TYPE"
    test_units = "none"
    test_phy = REG_PHY.NONE
    test_subnode = 0
    test_storage = 1
    test_reg_range = (-20, 20)
    test_labels = "Monitoring trigger type"
    test_enums = [{'0': 'TRIGGER_EVENT_AUTO', '1': 'TRIGGER_EVENT_FORCED'}]
    test_enums_count = 2
    test_cat_id = "MONITORING"
    test_scat_id = "SUB_CATEGORY_TEST"
    test_internal_use = "No description (invent here)"
    test_address_type = REG_ADDRESS_TYPE.NVM
    register = EthernetRegister(test_addr, test_dtype, test_access, test_identification,
                                test_units, test_cyclic, test_phy, test_subnode, test_storage,
                                test_reg_range, test_labels, test_enums, test_enums_count,
                                test_cat_id, test_scat_id, test_internal_use, test_address_type)

    assert register.identifier == test_identification
    assert register.units == test_units
    assert register.cyclic == test_cyclic
    assert register.address == test_addr
    assert register.dtype == test_dtype
    assert register.access == test_access
    assert register.phy == test_phy
    assert register.subnode == test_subnode
    assert register.storage == test_storage
    assert register.range == test_reg_range
    assert register.labels == test_labels
    assert register.address_type == test_address_type

    test_aux_enums = []
    for test_enum in test_enums:
        for key, value in test_enum.items():
            test_dictionary = {'label': value, 'value': int(key)}
            test_aux_enums.append(test_dictionary)

    assert register.enums == test_aux_enums
    assert register.enums_count == test_enums_count
    assert register.cat_id == test_cat_id
    assert register.scat_id == test_scat_id
    assert register.internal_use == test_internal_use


@pytest.mark.smoke
@pytest.mark.parametrize("test2_dtype", [REG_DTYPE.S8, REG_DTYPE.FLOAT, REG_DTYPE.DOMAIN, "Other type"])
@pytest.mark.parametrize("test2_storage", [None, 1])
def test_storage_dtype(test2_dtype, test2_storage):
    enums_count = [{'0': 'TRIGGER_EVENT_AUTO', '1': 'TRIGGER_EVENT_FORCED'}]
    # dtype test conditional
    if not isinstance(test2_dtype, REG_DTYPE):
        with pytest.raises(exc.ILValueError):
            EthernetRegister(0x58F0, test2_dtype, REG_ACCESS.RW, "MON_CFG_SOC_TYPE",
                             "none", "CONFIG", REG_PHY.NONE, 1, test2_storage,
                             (-20, 20), "Monitoring trigger type", enums_count,
                             "MONITORING", "SUB_CATEGORY_TEST", "No description (invent here)")

    else:
        register = EthernetRegister(0x58F0, test2_dtype, REG_ACCESS.RW, "MON_CFG_SOC_TYPE",
                                    "none", "CONFIG", REG_PHY.NONE, 1, test2_storage,
                                    (-20, 20), "Monitoring trigger type", enums_count,
                                    "MONITORING", "SUB_CATEGORY_TEST", "No description (invent here)")
        # storage test conditional
        if test2_dtype in [REG_DTYPE.S8, REG_DTYPE.U8, REG_DTYPE.S16,
                           REG_DTYPE.U16, REG_DTYPE.S32, REG_DTYPE.U32,
                           REG_DTYPE.S64, REG_DTYPE.U64, REG_DTYPE.FLOAT]:
            assert register.storage == test2_storage
        else:
            assert register.storage is None


@pytest.mark.smoke
@pytest.mark.parametrize("test2_range", [(None, None), (-20, 20)])
@pytest.mark.parametrize("test3_dtype", [REG_DTYPE.S8, REG_DTYPE.FLOAT])
def test_range_ethernet_register(test2_range, test3_dtype):
    enums = [{'0': 'TRIGGER_EVENT_AUTO', '1': 'TRIGGER_EVENT_FORCED'}]
    register = EthernetRegister(0x58F0, test3_dtype, REG_ACCESS.RW, "MON_CFG_SOC_TYPE",
                                "none", "CONFIG", REG_PHY.NONE, 1, 1,
                                test2_range, "Monitoring trigger type", enums, len(enums),
                                "MONITORING", "SUB_CATEGORY_TEST", "No description (invent here)")

    if test2_range == (None, None):
        test_aux_range = (
            dtypes_ranges[test3_dtype]["min"],
            dtypes_ranges[test3_dtype]["max"],
        )
    elif test3_dtype == REG_DTYPE.FLOAT:
        test_aux_range = (
            float(test2_range[0]),
            float(test2_range[1])
        )
    else:
        test_aux_range = (
            int(test2_range[0]),
            int(test2_range[1])
        )

    if len(register.range) == len(test_aux_range):
        for i in range(len(test_aux_range)):
            assert isinstance(register.range[i], type(test_aux_range[i])) is True
    assert register.range == test_aux_range
