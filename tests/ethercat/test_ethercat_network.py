import contextlib

with contextlib.suppress(ImportError):
    import pysoem
import pytest

from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.exceptions import ILError, ILFirmwareLoadError


@pytest.mark.docker()
def test_raise_exception_if_not_winpcap():
    try:
        import pysoem  # noqa: F401

        pytest.skip("WinPcap is installed")
    except ImportError:
        pass
    with pytest.raises(ImportError):
        EthercatNetwork("dummy_ifname")


@pytest.mark.ethercat()
def test_load_firmware_file_not_found_error(read_config):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])
    with pytest.raises(FileNotFoundError):
        net.load_firmware("ethercat.sfu", boot_in_app=True)


@pytest.mark.ethercat()
def test_load_firmware_no_slave_detected_error(mocker, read_config):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])
    mocker.patch("os.path.isfile", return_value=True)
    with pytest.raises(
        ILFirmwareLoadError,
        match="The firmware file could not be loaded correctly. No ECAT slave detected",
    ):
        net.load_firmware("dummy_file.lfu", boot_in_app=False, slave_id=23)


@pytest.mark.ethercat()
def test_wrong_interface_name_error(read_config):
    net = EthercatNetwork("not existing ifname")
    slave_id = 1
    dictionary = read_config["ethernet"]["dictionary"]
    with pytest.raises(ConnectionError):
        net.connect_to_slave(slave_id, dictionary)


@pytest.mark.ethercat()
def test_load_firmware_not_implemented_error(mocker, read_config):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])
    mocker.patch("os.path.isfile", return_value=True)
    mocker.patch("sys.platform", return_value="linux")
    with pytest.raises(NotImplementedError):
        net.load_firmware("dummy_file.lfu", boot_in_app=False)


@pytest.mark.ethercat()
@pytest.mark.parametrize("slave_id", [-1, "one", None])
def test_connect_to_slave_invalid_id(read_config, slave_id):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])
    with pytest.raises(ValueError, match="Invalid slave ID value"):
        net.connect_to_slave(slave_id, read_config["ethercat"]["dictionary"])


@pytest.mark.ethercat()
def test_connect_to_no_detected_slave(read_config):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])
    slaves = net.scan_slaves()
    slave_id = slaves[-1] + 1

    with pytest.raises(ILError):
        net.connect_to_slave(slave_id, read_config["ethercat"]["dictionary"])


@pytest.mark.ethercat()
def test_scan_slaves_raises_exception_if_drive_is_already_connected(connect_to_slave):
    servo, net = connect_to_slave
    net._ecat_master.read_state()
    assert servo.slave.state_check(pysoem.PREOP_STATE) == pysoem.PREOP_STATE
    with pytest.raises(ILError):
        net.scan_slaves()
    assert servo.slave.state_check(pysoem.PREOP_STATE) == pysoem.PREOP_STATE


@pytest.mark.ethercat()
def test_scan_slaves_info(read_config, get_configuration_from_rack_service):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])
    slaves_info = net.scan_slaves_info()

    drive_idx, config = get_configuration_from_rack_service
    drive = config[drive_idx]

    assert len(slaves_info) > 0
    assert read_config["ethercat"]["slave"] in slaves_info
    assert slaves_info[read_config["ethercat"]["slave"]].product_code == drive.product_code
    assert slaves_info[read_config["ethercat"]["slave"]].revision_number == drive.revision_number
