try:
    import pysoem
except ImportError:
    pass
import pytest

from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.exceptions import ILFirmwareLoadError, ILError


@pytest.mark.docker
def test_raise_exception_if_not_winpcap():
    try:
        import pysoem

        pytest.skip("WinPcap is installed")
    except ImportError:
        pass
    with pytest.raises(ImportError):
        EthercatNetwork("dummy_ifname")


@pytest.mark.ethercat
def test_load_firmware_file_not_found_error(read_config):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])
    with pytest.raises(FileNotFoundError):
        net.load_firmware(fw_file="ethercat.sfu")


@pytest.mark.ethercat
def test_load_firmware_no_slave_detected_error(mocker, read_config):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])
    mocker.patch("os.path.isfile", return_value=True)
    with pytest.raises(
        ILFirmwareLoadError,
        match="The firmware file could not be loaded correctly. No ECAT slave detected",
    ):
        net.load_firmware(fw_file="dummy_file.lfu", slave_id=23)


@pytest.mark.ethercat
def test_wrong_interface_name_error(read_config):
    with pytest.raises(ConnectionError):
        net = EthercatNetwork("not existing ifname")
        slave_id = 1
        dictionary = read_config["ethernet"]["dictionary"]
        net.connect_to_slave(slave_id, dictionary)


@pytest.mark.ethercat
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


@pytest.mark.ethercat
def test_scan_slaves_keeps_already_connected_slaves_state(connect_to_slave):
    servo, net = connect_to_slave
    net._ecat_master.read_state()
    assert servo.slave.state_check(pysoem.PREOP_STATE) == pysoem.PREOP_STATE
    net.scan_slaves()
    assert servo.slave.state_check(pysoem.PREOP_STATE) == pysoem.PREOP_STATE
