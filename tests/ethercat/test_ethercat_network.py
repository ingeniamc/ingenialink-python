import pytest

from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.exceptions import ILFirmwareLoadError


@pytest.mark.no_connection
def test_load_firmware_file_not_found_error(read_config):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])
    with pytest.raises(FileNotFoundError):
        net.load_firmware(fw_file="ethercat.sfu")


@pytest.mark.no_connection
def test_load_firmware_no_slave_detected_error(mocker, read_config):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])
    mocker.patch("os.path.isfile", return_value=True)
    with pytest.raises(
        ILFirmwareLoadError,
        match="The firmware file could not be loaded correctly. No ECAT slave detected",
    ):
        net.load_firmware(fw_file="dummy_file.lfu", slave_id=23)


@pytest.mark.no_connection
def test_wrong_interface_name_error():
    with pytest.raises(ConnectionError):
        EthercatNetwork("not existing ifname")


@pytest.mark.no_connection
def test_load_firmware_not_implemented_error(mocker, read_config):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])
    mocker.patch("os.path.isfile", return_value=True)
    mocker.patch("sys.platform", return_value="linux")
    with pytest.raises(NotImplementedError):
        net.load_firmware(fw_file="dummy_file.lfu")
