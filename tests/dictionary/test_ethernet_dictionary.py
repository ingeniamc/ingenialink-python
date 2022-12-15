import pytest

from ingenialink.ethernet.dictionary import EthernetDictionary
from ingenialink.constants import SINGLE_AXIS_MINIMUM_SUBNODES
from ingenialink.register import REG_DTYPE, REG_ACCESS, REG_PHY, dtypes_ranges


@pytest.mark.smoke
@pytest.mark.parametrize(
    "test_file_xdf, expected_num_registers",
    [
        ("test_dict_eth_1.xdf", 523),
        ("test_dict_eth_2.xdf", 519),
        ("test_dict_eth_axis_1.xdf", 78),
    ],
)
def test_registers_dictionary(test_file_xdf, expected_num_registers):
    # Count the number of registers in a EthernetDictionary instance
    test_ethernet_dict = EthernetDictionary(
        f"./tests/resources/ethernet/{test_file_xdf}"
    )
    test_num_registers = 0
    for current_subnode in range(test_ethernet_dict.subnodes):
        test_num_registers += len(test_ethernet_dict.registers(current_subnode))

    assert test_num_registers == expected_num_registers


@pytest.mark.smoke
@pytest.mark.parametrize(
    "test_file_xdf, expected_num_categories",
    [
        ("test_dict_eth_1.xdf", 19),
        ("test_dict_eth_2.xdf", 19),
        ("test_dict_eth_axis_1.xdf", 7),
    ],
)
def test_categories_dictionary(test_file_xdf, expected_num_categories):
    # Count the number of categories in a EthernetDictionary instance
    test_ethernet_dict = EthernetDictionary(
        f"./tests/resources/ethernet/{test_file_xdf}"
    )
    test_num_categories = len(test_ethernet_dict.categories.category_ids)

    assert test_num_categories == expected_num_categories


@pytest.mark.smoke
@pytest.mark.parametrize(
    "test_file_xdf, expected_num_errors",
    [
        ("test_dict_eth_1.xdf", 71),
        ("test_dict_eth_2.xdf", 71),
        ("test_dict_eth_axis_1.xdf", 13),
    ],
)
def test_errors_dictionary(test_file_xdf, expected_num_errors):
    # Count the number of errors in a EthernetDictionary instance
    test_ethernet_dict = EthernetDictionary(
        f"./tests/resources/ethernet/{test_file_xdf}"
    )
    test_num_errors = len(test_ethernet_dict.errors.errors)

    assert test_num_errors == expected_num_errors


@pytest.mark.smoke
def test_instance_dictionary():
    ethernet_dict = EthernetDictionary(
        f"./tests/resources/ethernet/test_dict_eth_1.xdf"
    )

    assert ethernet_dict.subnodes == SINGLE_AXIS_MINIMUM_SUBNODES

    regs_sub0 = ethernet_dict.registers(0)
    assert len(regs_sub0) == 84
    regs_sub1 = ethernet_dict.registers(1)
    assert len(regs_sub1) == 439

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
    assert regs_sub1.get(test_id).range == (
        dtypes_ranges[REG_DTYPE.FLOAT]["min"],
        dtypes_ranges[REG_DTYPE.FLOAT]["max"],
    )
