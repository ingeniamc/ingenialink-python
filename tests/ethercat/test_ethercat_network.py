import contextlib

with contextlib.suppress(ImportError):
    import pysoem
import atexit

import pytest

import ingenialink.ethercat.network
from ingenialink.ethercat.network import (
    ETHERCAT_NETWORK_REFERENCES,
    EthercatNetwork,
    GilReleaseConfig,
    release_network_reference,
)
from ingenialink.exceptions import ILError


@pytest.mark.docker
def test_raise_exception_if_not_winpcap():
    try:
        import pysoem  # noqa: F401

        pytest.skip("WinPcap is installed")
    except ImportError:
        pass
    with pytest.raises(ImportError):
        EthercatNetwork("dummy_ifname")


@pytest.mark.ethercat
def test_load_firmware_file_not_found_error(read_config):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])
    with pytest.raises(FileNotFoundError):
        net.load_firmware("ethercat.sfu", True)


@pytest.mark.ethercat
def test_load_firmware_no_slave_detected_error(mocker, read_config):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])
    mocker.patch("os.path.isfile", return_value=True)
    slave_id = 23
    with pytest.raises(
        ILError,
        match=f"Slave {slave_id} was not found.",
    ):
        net.load_firmware("dummy_file.lfu", False, slave_id=slave_id)


@pytest.mark.ethercat
def test_wrong_interface_name_error(read_config):
    with pytest.raises(ConnectionError):
        net = EthercatNetwork("not existing ifname")
        slave_id = 1
        dictionary = read_config["ethernet"]["dictionary"]
        net.connect_to_slave(slave_id, dictionary)


@pytest.mark.ethercat
@pytest.mark.parametrize("slave_id", [-1, "one", None])
def test_connect_to_slave_invalid_id(read_config, slave_id):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])
    with pytest.raises(ValueError):
        net.connect_to_slave(slave_id, read_config["ethercat"]["dictionary"])


@pytest.mark.ethercat
def test_connect_to_no_detected_slave(read_config):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])
    slaves = net.scan_slaves()
    slave_id = slaves[-1] + 1

    with pytest.raises(ILError):
        net.connect_to_slave(slave_id, read_config["ethercat"]["dictionary"])


@pytest.mark.ethercat
def test_scan_slaves_raises_exception_if_drive_is_already_connected(connect_to_slave):
    servo, net = connect_to_slave
    net._ecat_master.read_state()
    assert servo.slave.state_check(pysoem.PREOP_STATE) == pysoem.PREOP_STATE
    with pytest.raises(ILError):
        net.scan_slaves()
    assert servo.slave.state_check(pysoem.PREOP_STATE) == pysoem.PREOP_STATE


@pytest.mark.ethercat
def test_scan_slaves_info(read_config, get_drive_configuration_from_rack_service):
    net = EthercatNetwork(read_config["ethercat"]["ifname"])
    slaves_info = net.scan_slaves_info()

    drive = get_drive_configuration_from_rack_service

    assert len(slaves_info) > 0
    assert read_config["ethercat"]["slave"] in slaves_info
    assert slaves_info[read_config["ethercat"]["slave"]].product_code == drive.product_code
    assert slaves_info[read_config["ethercat"]["slave"]].revision_number == drive.revision_number


@pytest.mark.ethercat
def test_update_sdo_timeout(connect_to_slave):
    _, net = connect_to_slave
    read_timeout = 10
    write_timeout = 100
    net.update_sdo_timeout(read_timeout, write_timeout)
    assert net._ecat_master.sdo_read_timeout == read_timeout
    assert net._ecat_master.sdo_write_timeout == write_timeout
    default_timeout = int(net.DEFAULT_ECAT_CONNECTION_TIMEOUT_S * 1_000_000)
    net.update_sdo_timeout(default_timeout, default_timeout)
    assert net._ecat_master.sdo_read_timeout == default_timeout
    assert net._ecat_master.sdo_write_timeout == default_timeout


@pytest.mark.ethercat
def test_update_pysoem_timeouts(connect_to_slave):
    _, net = connect_to_slave
    old_ret = pysoem.settings.timeouts.ret
    old_safe = pysoem.settings.timeouts.safe
    old_eeprom = pysoem.settings.timeouts.eeprom
    old_tx_mailbox = pysoem.settings.timeouts.tx_mailbox
    old_rx_mailbox = pysoem.settings.timeouts.rx_mailbox
    old_state = pysoem.settings.timeouts.state
    net.update_pysoem_timeouts(1, 2, 3, 4, 5, 6)
    assert pysoem.settings.timeouts.ret == 1
    assert pysoem.settings.timeouts.safe == 2
    assert pysoem.settings.timeouts.eeprom == 3
    assert pysoem.settings.timeouts.tx_mailbox == 4
    assert pysoem.settings.timeouts.rx_mailbox == 5
    assert pysoem.settings.timeouts.state == 6
    net.update_pysoem_timeouts(
        old_ret, old_safe, old_eeprom, old_tx_mailbox, old_rx_mailbox, old_state
    )
    assert pysoem.settings.timeouts.ret == old_ret
    assert pysoem.settings.timeouts.safe == old_safe
    assert pysoem.settings.timeouts.eeprom == old_eeprom
    assert pysoem.settings.timeouts.tx_mailbox == old_tx_mailbox
    assert pysoem.settings.timeouts.rx_mailbox == old_rx_mailbox
    assert pysoem.settings.timeouts.state == old_state


@pytest.mark.ethercat
def test_check_node_state(connect_to_slave):
    servo, net = connect_to_slave
    # True when list is not empty
    assert net._check_node_state(servo, pysoem.PREOP_STATE)
    # False when list is not empty
    assert not net._check_node_state([], pysoem.PREOP_STATE)


@pytest.mark.no_connection
def test_gil_configuration():
    gil_config_1 = GilReleaseConfig.always()
    assert all([
        gil_config_1.config_init,
        gil_config_1.sdo_read_write,
        gil_config_1.foe_read_write,
        gil_config_1.send_receive_processdata,
    ])
    assert gil_config_1.always_release is True

    gil_config_2 = GilReleaseConfig(
        config_init=True, foe_read_write=False, send_receive_processdata=True
    )
    assert gil_config_2.config_init is True
    assert gil_config_2.sdo_read_write is None
    assert gil_config_2.foe_read_write is False
    assert gil_config_2.send_receive_processdata is True
    assert gil_config_2.always_release is False

    gil_config_3 = GilReleaseConfig()
    assert gil_config_3.config_init is None
    assert gil_config_3.sdo_read_write is None
    assert gil_config_3.foe_read_write is None
    assert gil_config_3.send_receive_processdata is None
    assert gil_config_3.always_release is False


@pytest.mark.no_connection
def test_release_network_reference_raises_error_if_wrong_network():
    class DummyEthercatNetwork:
        pass

    with pytest.raises(RuntimeError):
        release_network_reference(network=DummyEthercatNetwork)


@pytest.mark.ethercat
def test_master_reference_is_kept_while_network_is_alive(mocker):
    set_network_reference_spy = mocker.spy(ingenialink.ethercat.network, "set_network_reference")
    release_network_reference_spy = mocker.spy(
        ingenialink.ethercat.network, "release_network_reference"
    )

    assert not len(ETHERCAT_NETWORK_REFERENCES)
    net_1 = EthercatNetwork("dummy_network_1", gil_release_config=GilReleaseConfig.always())
    assert set_network_reference_spy.call_count == 1
    assert len(ETHERCAT_NETWORK_REFERENCES) == 1
    assert net_1 in ETHERCAT_NETWORK_REFERENCES

    # Create a second network
    net_2 = EthercatNetwork("dummy_network_2", gil_release_config=GilReleaseConfig.always())
    assert set_network_reference_spy.call_count == 2
    assert len(ETHERCAT_NETWORK_REFERENCES) == 2
    assert net_1 in ETHERCAT_NETWORK_REFERENCES
    assert net_2 in ETHERCAT_NETWORK_REFERENCES

    # Disconnect the first network so that the reference is cleared
    net_1.close_ecat_master()
    assert release_network_reference_spy.call_count == 1
    assert len(ETHERCAT_NETWORK_REFERENCES) == 1

    # Lose the reference to the second network, it should still exist in the stack
    net_2_id = id(net_2)
    net_2 = None
    assert id(list(ETHERCAT_NETWORK_REFERENCES)[0]) == net_2_id
    assert release_network_reference_spy.call_count == 1  # Has not been called again

    # When the program ends, atexit should get rid of it
    # Manually call atexit functions -> should be called on normal program termination
    atexit._run_exitfuncs()
    assert not len(ETHERCAT_NETWORK_REFERENCES)
