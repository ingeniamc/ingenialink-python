import os
import pytest
import time

from ingenialink.utils._utils import get_drive_identification
from ingenialink.register import REG_ADDRESS_TYPE
from ingenialink.canopen.servo import CanopenServo


def _clean(filename):
    if os.path.isfile(filename):
        os.remove(filename)


@pytest.mark.canopen
@pytest.mark.ethernet
def test_save_configuration(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    filename = 'temp_config'

    servo.save_configuration(filename)

    assert os.path.isfile(filename)

    device, saved_registers = servo._read_configuration_file(filename)

    prod_code, rev_number = get_drive_identification(servo)
    if 'ProductCode' in device.attrib and prod_code is not None:
        assert int(device.attrib.get('ProductCode')) == prod_code
    if 'RevisionNumber' in device.attrib and rev_number is not None:
        assert int(device.attrib.get('RevisionNumber')) == rev_number

    assert device.attrib.get("PartNumber") == servo.dictionary.part_number
    assert device.attrib.get("Interface") == servo.dictionary.interface
    assert device.attrib.get("firmwareVersion") == servo.dictionary.firmware_version
    # TODO: check name and family? These are not stored at the dictionary

    assert len(saved_registers) > 0
    for saved_register in saved_registers:
        subnode = int(saved_register.attrib.get('subnode'))

        reg_id = saved_register.attrib.get('id')
        registers = servo.dictionary.registers(subnode=subnode)

        assert reg_id in registers

        storage = saved_register.attrib.get('storage')
        if storage is not None:
            assert storage == str(registers[reg_id].storage)
        else:
            assert registers[reg_id].storage is None

        access = saved_register.attrib.get('access')
        assert registers[reg_id].access == servo.dictionary.access_xdf_options[access]

        dtype = saved_register.attrib.get('dtype')
        assert registers[reg_id].dtype == servo.dictionary.dtype_xdf_options[dtype]

    _clean(filename)
 

@pytest.mark.canopen
@pytest.mark.ethernet
def test_load_configuration(connect_to_slave, read_config, pytestconfig):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    protocol = pytestconfig.getoption("--protocol")

    filename = read_config[protocol]['load_config_file']

    assert os.path.isfile(filename)

    servo.load_configuration(filename)

    _, loaded_registers = servo._read_configuration_file(filename)

    for register in loaded_registers:
        reg_id = register.attrib.get('id')
        storage = register.attrib.get('storage')
        access = register.attrib.get('access')
        if storage is None or access != 'rw':
            continue
        subnode = int(register.attrib.get('subnode'))
        dtype = register.attrib.get('dtype')

        if reg_id in servo.dictionary.registers(subnode):
            if servo.dictionary.registers(subnode)[reg_id].address_type == REG_ADDRESS_TYPE.NVM_NONE:
                continue
            value = servo.read(reg_id, subnode=subnode)
            if dtype == 'str':
                assert value == storage
            elif dtype == 'float':
                assert value == pytest.approx(float(storage), 0.0001)
            else:
                assert value == int(storage)


@pytest.mark.no_connection
def test_read_configuration_file(read_config):
    test_file = "./tests/resources/test_config_file.xcf"
    servo = CanopenServo("test", 0, dictionary_path=read_config["canopen"]["dictionary"])
    device, registers = servo._read_configuration_file(test_file)

    assert device.attrib.get("PartNumber") == "EVE-NET-C"
    assert device.attrib.get("Interface") == "CAN"
    assert device.attrib.get("firmwareVersion") == "2.3.0"
    assert device.attrib.get('ProductCode') == "493840"
    assert device.attrib.get('RevisionNumber') == "196634"
    assert device.attrib.get('family') == "Summit"
    assert device.attrib.get('name') == "Generic"

    assert len(registers) == 4
    assert registers[0].get("id") == "DRV_DIAG_ERROR_LAST_COM"
    assert registers[0].get("access") == "r"
    assert registers[0].get("address") == "0x580F00"
    assert registers[0].get("dtype") == "s32"
    assert registers[0].get("subnode") == "0"


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_store_parameters(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    servo.store_parameters()

    value = servo.read('DRV_STATE_STATUS')
    assert value is not None

    # TODO: add a power cycle if possible to check the NVM


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_restore_parameters(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    servo.restore_parameters()

    value = servo.read('DRV_STATE_STATUS')
    assert value is not None

    # TODO: add a power cycle if possible to check the NVM


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_read(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    value = servo.read('DRV_STATE_STATUS')
    assert value is not None


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_write(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    reg = 'CL_AUX_FBK_SENSOR'
    value = 4

    saved_value = servo.read(reg)
    value = value + 1 if saved_value == value else value
    
    servo.write(reg, value)
    saved_value = servo.read(reg)

    assert value == saved_value
