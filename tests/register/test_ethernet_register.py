import pytest

from ingenialink.ethernet.dictionary import EthernetDictionary
from ingenialink.ethernet.register import EthernetRegister
from ingenialink.register import REG_DTYPE, REG_ACCESS, REG_PHY


@pytest.mark.ethernet
def test_canopen_register(connect_to_slave):
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
    assert register.idx == 0x2014
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
