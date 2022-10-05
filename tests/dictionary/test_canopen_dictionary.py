import pytest
from tests.conftest import read_config
from ingenialink.canopen.dictionary import CanopenDictionary


@pytest.mark.smoke
def test_get_register_dictionary(read_config):
    file_test_path = read_config['canopen']['dictionary']
    canopen_dict = CanopenDictionary(file_test_path)

    assert canopen_dict.subnodes == 2

    regs_sub0 = canopen_dict.registers(0)
    assert len(regs_sub0) == 167 - 1
    regs_sub1 = canopen_dict.registers(1)
    assert len(regs_sub1) == 510
