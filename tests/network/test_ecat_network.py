import pytest

from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.exceptions import ILFirmwareLoadError


@pytest.mark.ethercat
def test_scan_slaves(read_config):
    net = EthercatNetwork(read_config['ethercat']['ifname'])

    slaves = net.scan_slaves()
    assert len(slaves) > 0


@pytest.mark.ethercat
def test_load_firmware_file_not_found(read_config):
    net = EthercatNetwork(read_config['ethercat']['ifname'])
    with pytest.raises(FileNotFoundError):
        net.load_firmware(fw_file="ethercat.sfu")

 
@pytest.mark.ethercat
def test_load_firmware_load_error(mocker, read_config):
    net = EthercatNetwork(read_config['ethercat']['ifname'])
    mocker.patch('os.path.isfile', return_value=True)
    with pytest.raises(ILFirmwareLoadError):
        net.load_firmware(fw_file="ethercat.sfu")


@pytest.mark.ethercat
def test_load_firmware_value_error(mocker, read_config):
    net = EthercatNetwork(read_config['ethercat']['ifname'])
    mocker.patch('os.path.isfile', return_value=True)
    with pytest.raises(ValueError):
        net.load_firmware(fw_file="ethercat.xyz")
