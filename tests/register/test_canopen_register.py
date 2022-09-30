import pytest

from ingenialink.canopen.dictionary import CanopenDictionary
from ingenialink.canopen.register import CanopenRegister
from ingenialink.register import REG_DTYPE, REG_ACCESS, REG_PHY


@pytest.mark.develop
@pytest.mark.canopen
@pytest.mark.parametrize("test_identification, test_units, test_cyclic, test_idx, test_subidx, "
                         "test_dtype, test_access, test_phy, test_subnode, test_storage,"
                         "test_reg_range, test_labels, test_enums, test_enums_count, "
                         "test_cat_id, test_scat_id, test_internal_use",
                         [("MON_CFG_SOC_TYPE", "none", "CONFIG", 0x58F0, 0x00,
                           REG_DTYPE.U32, REG_ACCESS.RW, REG_PHY.NONE, 0, 1,
                           (-20, 20), "Monitoring trigger type",
                           [{'0': 'TRIGGER_EVENT_AUTO', '1': 'TRIGGER_EVENT_FORCED'}],
                           2, "MONITORING", "SUB_CATEGORY_TEST", "No description (invent here)")])
def test_getters_canopen_register(test_identification, test_units,test_cyclic, test_idx, test_subidx,
                                  test_dtype, test_access, test_phy, test_subnode, test_storage,
                                  test_reg_range, test_labels, test_enums, test_enums_count,
                                  test_cat_id, test_scat_id, test_internal_use):

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


# @pytest.mark.develop
# @pytest.mark.canopen
# @pytest.mark.parametrize("dtypes", [REG_DTYPE.U8, REG_DTYPE.S8, REG_DTYPE.U16, REG_DTYPE.S16,
#                                     REG_DTYPE.U32, REG_DTYPE.S32, REG_DTYPE.U64, REG_DTYPE.S64,
#                                     REG_DTYPE.STR, REG_DTYPE.DOMAIN])
# @pytest.mark.parametrize("reg_ranges", [(None, None), (-20, 20)])
# def test_canopen_register_range(dtypes, reg_ranges):
#     register = CanopenRegister('DRV_OP_CMD', '-', 'CYCLIC_RX', 0x2014, 0,
#                                REG_DTYPE.U16, REG_ACCESS.RW, reg_ranges=reg_ranges)
#
#     register.range()


@pytest.mark.develop
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


