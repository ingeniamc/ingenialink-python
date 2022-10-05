import pytest
from ingenialink.ethernet.dictionary import EthernetDictionary
from ingenialink.register import REG_DTYPE, REG_ACCESS, REG_PHY, dtypes_ranges


@pytest.mark.smoke
def test_instance_dictionary(read_config):
    file_test_path = read_config['ethernet']['dictionary']
    ethernet_dict = EthernetDictionary(file_test_path)

    assert ethernet_dict.subnodes == 2

    regs_sub0 = ethernet_dict.registers(0)
    assert len(regs_sub0) == 88
    regs_sub1 = ethernet_dict.registers(1)
    assert len(regs_sub1) == 464

    test_id = "DRV_PROT_MAN_OVER_VOLT"
    assert regs_sub1.get(test_id).identifier == "DRV_PROT_MAN_OVER_VOLT"
    assert regs_sub1.get(test_id).units == "V"
    assert regs_sub1.get(test_id).cyclic == "CONFIG"
    assert regs_sub1.get(test_id).address == 0x0712
    assert regs_sub1.get(test_id).dtype == REG_DTYPE.FLOAT
    assert regs_sub1.get(test_id).access == REG_ACCESS.RO
    assert regs_sub1.get(test_id).phy == REG_PHY.NONE
    assert regs_sub1.get(test_id).subnode == 1
    assert regs_sub1.get(test_id).storage is None
    assert regs_sub1.get(test_id).range == (dtypes_ranges[REG_DTYPE.FLOAT]["min"],
                                            dtypes_ranges[REG_DTYPE.FLOAT]["max"])
