import pytest
import xml.etree.ElementTree as ET

from ingenialink.canopen.dictionary import CanopenDictionary


@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.parametrize("test_file_xdf, expected_num_registers", [
    ("test_dict_can_1.xdf", 702),
    ("test_dict_can_2.xdf", 698),
    ("test_dict_can_axis_1.xdf", 16),
    ("test_dict_can_no_attr_reg.xdf", 0)
])
def test_registers_dictionary(test_file_xdf, expected_num_registers):
    # Count the number of registers in a CanopenDictionary instance
    test_canopen_dict = CanopenDictionary(f'./tests/resources/canopen/{test_file_xdf}')
    test_num_registers = 0
    for current_subnode in range(test_canopen_dict.subnodes):
        test_num_registers += len(test_canopen_dict.registers(current_subnode))

    assert test_num_registers == expected_num_registers

@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.parametrize("test_file_xdf, expected_num_categories", [
    ("test_dict_can_1.xdf", 20),
    ("test_dict_can_2.xdf", 20),
    ("test_dict_can_axis_1.xdf", 7)
])
def test_categories_dictionary(test_file_xdf, expected_num_categories):
    # Count the number of categories in a CanopenDictionary instance
    test_canopen_dict = CanopenDictionary(f'./tests/resources/canopen/{test_file_xdf}')
    test_num_categories = len(test_canopen_dict.categories.category_ids)

    assert test_num_categories == expected_num_categories


@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.parametrize("test_file_xdf, expected_num_errors", [
    ("test_dict_can_1.xdf", 71),
    ("test_dict_can_2.xdf", 71),
    ("test_dict_can_axis_1.xdf", 8)
])
def test_errors_dictionary(test_file_xdf, expected_num_errors):
    # Count the number of errors in a CanopenDictionary instance
    test_canopen_dict = CanopenDictionary(f'./tests/resources/canopen/{test_file_xdf}')
    test_num_errors = len(test_canopen_dict.errors.errors)

    assert test_num_errors == expected_num_errors
