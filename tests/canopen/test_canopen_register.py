import pytest

from ingenialink.canopen.dictionary import CanopenDictionary
from ingenialink.canopen.register import CanopenRegister, REG_DTYPE, REG_ACCESS, REG_PHY


@pytest.mark.no_connection
@pytest.mark.smoke
def test_getters_canopen_register():
    test_identification = "MON_CFG_SOC_TYPE"
    test_units = "none"
    test_cyclic = "CONFIG"
    test_idx = 0x58F0
    test_subidx = 0x00
    test_dtype = REG_DTYPE.U32
    test_access = REG_ACCESS.RW
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
    register = CanopenRegister(test_identification, test_units, test_cyclic, test_idx, test_subidx,
                               test_dtype, test_access, test_phy, test_subnode, test_storage,
                               test_reg_range, test_labels, test_enums, test_enums_count,
                               test_cat_id, test_scat_id, test_internal_use)

    assert register.identifier == test_identification
    assert register.units == test_units
    assert register.cyclic == test_cyclic
    assert register.idx == test_idx
    assert register.subidx == test_subidx
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


@pytest.mark.canopen
def test_canopen_connection_register(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    assert isinstance(servo.dictionary, CanopenDictionary)

    registers_sub_0 = servo.dictionary.registers(0)
    assert registers_sub_0 is not None
    registers_sub_1 = servo.dictionary.registers(1)
    assert registers_sub_1 is not None

    register = registers_sub_1.get('DRV_OP_CMD')
    assert isinstance(register, CanopenRegister)

    assert register.identifier == 'DRV_OP_CMD'
    assert register.units == '-'
    assert register.cyclic == 'CYCLIC_RX'
    assert register.dtype == REG_DTYPE.U16
    assert register.access, REG_ACCESS.RW
    assert register.idx == 0x2014
    assert register.subidx == 0
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


