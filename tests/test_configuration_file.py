import pytest

from ingenialink import RegAccess, RegDtype
from ingenialink.configuration_file import ConfigurationFile
from ingenialink.dictionary import Interface
from ingenialink.register import Register


@pytest.mark.no_connection
def test_from_xcf():
    test_file = "./tests/resources/test_config_file.xcf"
    conf_file = ConfigurationFile.from_xcf(test_file)
    assert conf_file.device.interface == Interface.CAN
    assert conf_file.device.part_number == "EVE-NET-C"
    assert conf_file.device.product_code == 493840
    assert conf_file.device.revision_number == 196634
    assert conf_file.device.firmware_version == "2.3.0"
    assert conf_file.device.node_id is None

    assert len(conf_file.registers) == 1  # Only 1 register has storage field
    assert conf_file.registers[0].dtype == RegDtype.U16
    assert conf_file.registers[0].access == RegAccess.RW
    assert conf_file.registers[0].uid == "DRV_DIAG_SYS_ERROR_TOTAL_COM"
    assert conf_file.registers[0].subnode == 0
    assert conf_file.registers[0].storage == 0


@pytest.mark.no_connection
def test_from_register():
    conf_file = ConfigurationFile.create_xcf(Interface.CAN, "a", 0, 0, "0.0.0")
    reg = Register(RegDtype.FLOAT, RegAccess.RW, "TEST_REG", subnode=2)
    conf_file.add_register(reg, 5.5)
    assert conf_file.registers[0].dtype == RegDtype.FLOAT
    assert conf_file.registers[0].access == RegAccess.RW
    assert conf_file.registers[0].uid == "TEST_REG"
    assert conf_file.registers[0].subnode == 2
    assert conf_file.registers[0].storage == 5.5


@pytest.mark.no_connection
def test_to_xcf_fail_no_device():
    with pytest.raises(ValueError):
        conf = ConfigurationFile.create_xcf(Interface.CAN, "a", 0, 0, "0.0.0")
        conf.to_xcf("test_path")
