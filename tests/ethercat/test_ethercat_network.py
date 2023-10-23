import pytest

from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.exceptions import ILFirmwareLoadError, ILError


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
        net = EthercatNetwork("not existing ifname")
        slave_id = 1
        net.connect_to_slave(slave_id)


@pytest.mark.no_connection
def test_load_firmware_not_implemented_error(mocker, read_config):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])
    mocker.patch("os.path.isfile", return_value=True)
    mocker.patch("sys.platform", return_value="linux")
    with pytest.raises(NotImplementedError):
        net.load_firmware(fw_file="dummy_file.lfu")


@pytest.mark.eoe
@pytest.mark.parametrize("slave_id", [-1, "one", None])
def test_connect_to_slave_invalid_id(read_config, slave_id):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])
    with pytest.raises(ValueError):
        net.connect_to_slave(slave_id)


@pytest.mark.eoe
def test_connect_to_slave_no_slaves_detected(mocker, read_config):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])

    def scan_slaves():
        return []

    mocker.patch.object(net, "scan_slaves", scan_slaves)
    with pytest.raises(ILError):
        net.connect_to_slave(1)
