import os
import pytest
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET
from ingenialink.exceptions import  ILError


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_save_configuration(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    filename = 'temp_config'

    servo.save_configuration(filename)

    assert os.path.isfile(filename)

    if os.path.isfile(filename):
        os.remove(filename)

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
def test_load_configuration_file_not_found(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    filename = 'can_config.xdf'
    with pytest.raises(FileNotFoundError):
        servo.load_configuration(filename)


@pytest.mark.parametrize('subnode', [
    -1, "1"
])
@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_load_configuration_invalid_subnode(read_config, pytestconfig, connect_to_slave, subnode):
    servo, net = connect_to_slave
    assert servo is not None and net is not None
    
    protocol = pytestconfig.getoption("--protocol")
    filename = read_config[protocol]['load_config_file']
    with pytest.raises(ValueError):
        servo.load_configuration(filename, subnode=subnode)


@pytest.mark.canopen
@pytest.mark.ethernet
def test_load_configuration_to_subnode_zero(read_config, pytestconfig, connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    protocol = pytestconfig.getoption("--protocol")
    filename = read_config[protocol]['load_config_file']
    path = Path(filename)
    file = filename.split('/')[-1]
    modified_path = Path(filename.replace(file, "config_0_test.xdf"))
    shutil.copy(path, modified_path)
    with open(modified_path, 'r', encoding='utf-8') as xml_file:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        axis = tree.findall('*/Device/Axes/Axis')
        if axis:
            # Multiaxis
            registers = root.findall(
                './Body/Device/Axes/Axis/Registers/Register'
            )
        else:
            # Single axis
            registers = root.findall('./Body/Device/Registers/Register')
        for element in registers:
            element.attrib['subnode'] = "1"
        tree.write(modified_path)
    with pytest.raises(ValueError):
        servo.load_configuration(str(modified_path), subnode=0)

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
