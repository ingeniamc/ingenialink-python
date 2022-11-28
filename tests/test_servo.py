import os
import xml.etree.ElementTree as ET

from ingenialink.utils._utils import get_drive_identification
from ingenialink.register import REG_ADDRESS_TYPE


def _clean(filename):
    if os.path.isfile(filename):
        os.remove(filename)


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_save_configuration(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    filename = 'temp_config'

    servo.save_configuration(filename)

    assert os.path.isfile(filename)

    with open(filename, 'r', encoding='utf-8') as xml_file:
        tree = ET.parse(xml_file)
    root = tree.getroot()

    device = root.find('Body/Device')
    prod_code, rev_number = get_drive_identification(servo)
    if 'ProductCode' in device.attrib and prod_code is not None:
        assert int(device.attrib.get('ProductCode')) == prod_code
    if 'RevisionNumber' in device.attrib and rev_number is not None:
        assert int(device.attrib.get('RevisionNumber')) == rev_number

    assert device.attrib.get("PartNumber") == servo.dictionary.part_number
    assert device.attrib.get("Interface") == servo.dictionary.interface
    assert device.attrib.get("firmwareVersion") == servo.dictionary.firmware_version
    # TODO: check name and family? These are not stored at the dictionary

    saved_registers = root.findall('./Body/Device/Registers/Register')
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

        assert access == "rw"
        assert registers[reg_id].address_type != REG_ADDRESS_TYPE.NVM_NONE

    _clean(filename)

@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_load_configuration(connect_to_slave, read_config, pytestconfig):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    protocol = pytestconfig.getoption("--protocol")

    filename = read_config[protocol]['load_config_file']

    assert os.path.isfile(filename)

    servo.load_configuration(filename)

@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_store_parameters(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    servo.store_parameters()

    value = servo.read('DRV_STATE_STATUS')
    assert value is not None

@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_restore_parameters(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    servo.restore_parameters()

    value = servo.read('DRV_STATE_STATUS')
    assert value is not None

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

    servo.write('CL_AUX_FBK_SENSOR', 4)
