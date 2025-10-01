from typing import ClassVar
from xml.etree import ElementTree

import pytest

import tests.resources
from ingenialink import RegAccess, RegDtype
from ingenialink.configuration_file import ConfigRegister, ConfigurationFile
from ingenialink.dictionary import Interface
from ingenialink.register import Register


class RegisterXCFElementFactory:
    DEFAULT_ATTRIBUTES: ClassVar[dict] = {
        ConfigRegister._ConfigRegister__ID_ATTR: "PROF_MAX_VEL",
        ConfigRegister._ConfigRegister__SUBNODE_ATTR: "1",
        ConfigRegister._ConfigRegister__DTYPE_ATTR: "float",
        ConfigRegister._ConfigRegister__ACCESS_ATTR: "rw",
        ConfigRegister._ConfigRegister__STORAGE_ATTR: "20.0",
    }

    @classmethod
    def create(cls, missing_attibute):
        attrs = cls.DEFAULT_ATTRIBUTES.copy()

        if missing_attibute is not None:
            attrs.pop(missing_attibute)

        return ElementTree.Element("Register", attrib=attrs)


@pytest.mark.no_connection
def test_from_xcf():
    test_file = tests.resources.TEST_CONFIG_FILE
    conf_file = ConfigurationFile.load_from_xcf(test_file)
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
    conf_file = ConfigurationFile.create_empty_configuration(Interface.CAN, "a", 0, 0, "0.0.0")
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
        conf = ConfigurationFile.create_empty_configuration(Interface.CAN, "a", 0, 0, "0.0.0")
        conf.save_to_xcf("test_path")


@pytest.mark.no_connection
@pytest.mark.parametrize("missing_attr", RegisterXCFElementFactory.DEFAULT_ATTRIBUTES.keys())
def test_config_register_from_xcf_missing_attribute(missing_attr):
    register_xcf_element = RegisterXCFElementFactory.create(missing_attr)
    with pytest.raises(ValueError) as exc_info:
        ConfigRegister.from_xcf(register_xcf_element)

    error_msg = str(exc_info.value)
    if missing_attr == ConfigRegister._ConfigRegister__ID_ATTR:
        assert error_msg == "Missing id attribute"
    else:
        assert (
            error_msg == f"Missing {missing_attr} attribute for register "
            f"{register_xcf_element.attrib.get('id')}."
        )
