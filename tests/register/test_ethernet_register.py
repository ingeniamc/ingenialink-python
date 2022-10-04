import pytest

from ingenialink.ethernet.dictionary import EthernetDictionary
from ingenialink.ethernet.register import EthernetRegister
from ingenialink.register import REG_DTYPE, REG_ACCESS, REG_PHY, dtypes_ranges
from ingenialink.utils._utils import *


@pytest.mark.develop
@pytest.mark.ethernet
@pytest.mark.parametrize("test_addr, test_dtype, test_access, test_identification, "
                         "test_units, test_cyclic, test_phy, test_subnode, test_storage,"
                         "test_reg_range, test_labels, test_enums, test_enums_count, "
                         "test_cat_id, test_scat_id, test_internal_use",
                         [(0x58F0, REG_DTYPE.U32, REG_ACCESS.RW, "MON_CFG_SOC_TYPE",
                           "none", "CONFIG", REG_PHY.NONE, 0, 1, (-20, 20), "Monitoring trigger type",
                           [{'0': 'TRIGGER_EVENT_AUTO', '1': 'TRIGGER_EVENT_FORCED'}],
                           2, "MONITORING", "SUB_CATEGORY_TEST", "No description (invent here)")])
def test_getters_ethernet_register(test_addr, test_dtype, test_access, test_identification,
                                   test_units, test_cyclic, test_phy, test_subnode, test_storage,
                                   test_reg_range, test_labels, test_enums, test_enums_count,
                                   test_cat_id, test_scat_id, test_internal_use):

    register = EthernetRegister(test_addr, test_dtype, test_access, test_identification,
                                test_units, test_cyclic, test_phy, test_subnode, test_storage,
                                test_reg_range, test_labels, test_enums, test_enums_count,
                                test_cat_id, test_scat_id, test_internal_use)

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


@pytest.mark.develop
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


@pytest.mark.develop
@pytest.mark.parametrize("test2_range", [(None, None), (-20, 20)])
@pytest.mark.parametrize("test3_dtype", [REG_DTYPE.S8, REG_DTYPE.FLOAT])
def test_range_ethernet_register(test2_range, test3_dtype):
    enums_count = [{'0': 'TRIGGER_EVENT_AUTO', '1': 'TRIGGER_EVENT_FORCED'}]
    register = EthernetRegister(0x58F0, test3_dtype, REG_ACCESS.RW, "MON_CFG_SOC_TYPE",
                                "none", "CONFIG", REG_PHY.NONE, 1, 1,
                                test2_range, "Monitoring trigger type", enums_count,
                                "MONITORING", "SUB_CATEGORY_TEST", "No description (invent here)")

    if test3_dtype == REG_DTYPE.FLOAT:
        test_aux_range = (
            float(test2_range[0]) if test2_range[0] else dtypes_ranges[test3_dtype]["min"],
            float(test2_range[1]) if test2_range[1] else dtypes_ranges[test3_dtype]["max"],
        )
    else:
        test_aux_range = (
            int(test2_range[0]) if test2_range[0] else dtypes_ranges[test3_dtype]["min"],
            int(test2_range[1]) if test2_range[1] else dtypes_ranges[test3_dtype]["max"],
        )

    if len(register.range) == len(test_aux_range):
        for i in range(len(test_aux_range)):
            assert isinstance(register.range[i], type(test_aux_range[i])) is True
    assert register.range == test_aux_range


@pytest.mark.ethernet
def test_ethernet_connection_register(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    assert isinstance(servo.dictionary, EthernetDictionary)

    registers_sub_0 = servo.dictionary.registers(0)
    assert registers_sub_0 is not None
    registers_sub_1 = servo.dictionary.registers(1)
    assert registers_sub_1 is not None

    register = registers_sub_1.get('DRV_OP_CMD')
    assert isinstance(register, EthernetRegister)

    assert register.identifier == 'DRV_OP_CMD'
    assert register.units == '-'
    assert register.cyclic == 'CYCLIC_RX'
    assert register.dtype == REG_DTYPE.U16
    assert register.access, REG_ACCESS.RW
    assert register.address == 0x2014
    assert register.phy == REG_PHY.NONE
    assert register.subnode == 1
    assert register.storage is None
    assert register.storage_valid == 0
    assert register.range == (0, 65535)
    assert register.labels is not None
    assert len(register.enums) == 13
    assert register.enums_count == 13
    assert register.cat_id == 'TARGET'
    assert register.scat_id is None
    assert register.internal_use == 0
