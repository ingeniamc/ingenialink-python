import contextlib

import tests.resources

with contextlib.suppress(ImportError):
    import pysoem
import random
import threading
import time
from typing import TYPE_CHECKING, cast

import numpy as np
import pytest
from summit_testing_framework.setups import (
    MultiRackServiceConfigSpecifier,
    RackServiceConfigSpecifier,
)

import ingenialink.ethercat.network
from ingenialink.ethercat.network import (
    ETHERCAT_NETWORK_REFERENCES,
    EthercatNetwork,
    GilReleaseConfig,
    release_network_reference,
)
from ingenialink.exceptions import ILError, ILFirmwareLoadError
from ingenialink.network import NetDevEvt, NetState
from ingenialink.pdo import PDOMap, RPDOMap, TPDOMap

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from ingenialink.ethercat.servo import EthercatServo


@pytest.fixture
def mocked_network_for_firmware_loading(mocker):
    net = EthercatNetwork("fake_interface")
    mocker.patch("os.path.isfile", return_value=True)
    mocker.patch.object(net, "_force_boot_mode")
    mocker.patch.object(net, "_start_master")
    mocker.patch.object(net, "_EthercatNetwork__init_nodes")

    mock_slave = mocker.Mock()
    net._ecat_master.slaves = [mock_slave]
    net._EthercatNetwork__last_init_nodes = {1}
    yield net, mock_slave
    net.close_ecat_master()


@pytest.mark.no_pcap
def test_raise_exception_if_not_winpcap():
    try:
        import pysoem  # noqa: F401

        pytest.fail("WinPcap appears to be installed and thus the test cannot be executed.")
    except ImportError:
        pass
    previous_networks = ETHERCAT_NETWORK_REFERENCES.copy()
    with pytest.raises(ImportError):
        EthercatNetwork("dummy_ifname")
    release_networks = [net for net in ETHERCAT_NETWORK_REFERENCES if net not in previous_networks]
    for net in release_networks:
        release_network_reference(net)


def test_load_firmware_file_not_found_error():
    net = EthercatNetwork("fake_interface")
    with pytest.raises(FileNotFoundError):
        net.load_firmware("ethercat.sfu", True)
    net.close_ecat_master()


def test_load_firmware_no_slave_detected_error(mocked_network_for_firmware_loading):
    net, _ = mocked_network_for_firmware_loading
    slave_id = 23
    with pytest.raises(
        ILError,
        match=f"Slave {slave_id} was not found.",
    ):
        net.load_firmware("dummy_file.lfu", False, slave_id=slave_id)


@pytest.mark.ethercat
def test_find_adapters(setup_descriptor):
    """Test that find_adapters returns a list of EtherCATNetwork instances."""
    adapter_found = False
    ifname = setup_descriptor.ifname
    for adapter in EthercatNetwork.find_adapters():
        _, interface_guid, _ = adapter
        interface_guid = f"\\Device\\NPF_{interface_guid}"
        if interface_guid == ifname:
            adapter_found = True
            break
    assert adapter_found is True


def test_load_firmware_boot_state_failure(mocker, mocked_network_for_firmware_loading):
    net, _ = mocked_network_for_firmware_loading
    mocker.patch.object(net, "_switch_to_boot_state", side_effect=[True, False])
    mocker.patch.object(net, "_write_foe", return_value=-5)
    with pytest.raises(
        ILFirmwareLoadError,
        match="The firmware file could not be loaded correctly after 2 attempts. "
        "Errors:\nAttempt 1: FoE error.\n"
        "Attempt 2: The slave cannot reach the Boot state.",
    ):
        net.load_firmware("dummy_file.sfu", False, slave_id=1)


def test_load_firmware_foe_write_failure(mocker, mocked_network_for_firmware_loading):
    net, _ = mocked_network_for_firmware_loading
    mocker.patch("os.path.isfile", return_value=True)
    mocker.patch.object(net, "_switch_to_boot_state", return_value=True)
    mocker.patch.object(net, "_write_foe", side_effect=[-5, -3])
    with pytest.raises(
        ILFirmwareLoadError,
        match="The firmware file could not be loaded correctly after 2 attempts. "
        "Errors:\nAttempt 1: FoE error.\nAttempt 2: Unexpected mailbox received.",
    ):
        net.load_firmware("dummy_file.sfu", False, slave_id=1)


def test_load_firmware_success_after_retry(mocker, mocked_network_for_firmware_loading):
    net, slave = mocked_network_for_firmware_loading
    mocker.patch.object(net, "_switch_to_boot_state", side_effect=[False, True])
    mocker.patch.object(net, "_write_foe", return_value=1)
    mocker.patch("time.sleep", return_value=None)
    slave.state_check.return_value = pysoem.PREOP_STATE
    net.load_firmware("dummy_file.sfu", False, slave_id=1)


def test_wrong_interface_name_error():
    net = EthercatNetwork("fake_interface")
    slave_id = 1
    dictionary = "fake_dictionary.xdf"
    with pytest.raises(ConnectionError):
        net.connect_to_slave(slave_id, dictionary)
    net.close_ecat_master()


@pytest.mark.ethercat
@pytest.mark.parametrize("slave_id", [-1, "one", None])
def test_connect_to_slave_invalid_id(setup_descriptor, slave_id):
    net = EthercatNetwork(setup_descriptor.ifname)
    with pytest.raises(ValueError):
        net.connect_to_slave(slave_id, setup_descriptor.dictionary)
    net.close_ecat_master()


@pytest.mark.ethercat
def test_connect_to_no_detected_slave(setup_descriptor):
    net = EthercatNetwork(setup_descriptor.ifname)
    slaves = net.scan_slaves()
    slave_id = slaves[-1] + 1

    with pytest.raises(ILError):
        net.connect_to_slave(slave_id, setup_descriptor.dictionary)
    net.close_ecat_master()


@pytest.mark.ethercat
def test_connect_to_slave_with_callback(setup_descriptor):
    disconnected_servos = []

    def dummy_callback(servo):
        disconnected_servos.append(servo.slave_id)

    net = EthercatNetwork(setup_descriptor.ifname)
    servo = net.connect_to_slave(
        setup_descriptor.slave,
        setup_descriptor.dictionary,
        disconnect_callback=dummy_callback,
    )
    assert servo is not None
    assert servo.target == setup_descriptor.slave

    # Disconnect the servo to trigger the callback
    assert len(disconnected_servos) == 0
    net.disconnect_from_slave(servo)  # this closes the ecat master
    assert len(disconnected_servos) == 1
    assert disconnected_servos[0] == setup_descriptor.slave


@pytest.mark.ethercat
def test_scan_slaves_raises_exception_if_drive_is_already_connected(servo, net):
    net._ecat_master.read_state()
    assert servo.slave.state_check(pysoem.PREOP_STATE) == pysoem.PREOP_STATE
    with pytest.raises(ILError):
        net.scan_slaves()
    assert servo.slave.state_check(pysoem.PREOP_STATE) == pysoem.PREOP_STATE


@pytest.mark.ethercat
def test_scan_slaves_info(setup_specifier, setup_descriptor, request):
    if not isinstance(
        setup_specifier, (RackServiceConfigSpecifier, MultiRackServiceConfigSpecifier)
    ):
        pytest.skip("Only available for rack specifiers.")
    net = EthercatNetwork(setup_descriptor.ifname)
    slaves_info = net.scan_slaves_info()

    drive = request.getfixturevalue("get_drive_configuration_from_rack_service")

    assert len(slaves_info) > 0
    assert setup_descriptor.slave in slaves_info
    assert slaves_info[setup_descriptor.slave].product_code == drive.product_code
    net.close_ecat_master()


@pytest.mark.ethercat
def test_update_sdo_timeout(net):
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
def test_update_pysoem_timeouts(net):
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
def test_check_node_state(servo, net):
    # True when list is not empty
    assert net._check_node_state(servo, pysoem.PREOP_STATE)
    # False when list is not empty
    assert not net._check_node_state([], pysoem.PREOP_STATE)


def test_check_node_state_with_non_existent_slave(pysoem_mock_network):
    """Test that _check_node_state handles slaves with slave_exists=False.

    This verifies that the method doesn't crash when checking state of a servo
    whose slave reference has been set to None (slave doesn't exist).
    """
    net = EthercatNetwork("dummy_ifname")

    # Connect to 2 slaves
    servo1 = net.connect_to_slave(
        slave_id=1,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
    )
    servo2 = net.connect_to_slave(
        slave_id=2,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
    )

    # Both servos should initially have valid references
    assert servo1.slave_exists is True
    assert servo2.slave_exists is True

    # Simulate servo2 disappearing by shrinking the network to 1 slave
    pysoem_mock_network.set_num_slaves(1)
    net._EthercatNetwork__init_nodes()

    # servo2 should now have slave_exists = False
    assert servo1.slave_exists is True
    assert servo2.slave_exists is False

    # _check_node_state should handle a list containing a non-existent slave
    # It should return False because servo2 doesn't exist (can't check its state)
    assert not net._check_node_state([servo1, servo2], pysoem.INIT_STATE)

    # With only the existing servo, it should work normally (mock defaults to INIT_STATE)
    assert net._check_node_state([servo1], pysoem.INIT_STATE)

    net.close_ecat_master()


def test_change_nodes_state_with_non_existent_slave(pysoem_mock_network):
    """Test that _change_nodes_state handles slaves with slave_exists=False.

    This verifies that the method doesn't crash when trying to change state of a servo
    whose slave reference has been set to None (slave doesn't exist).
    """
    net = EthercatNetwork("dummy_ifname")

    # Connect to 3 slaves
    servo1 = net.connect_to_slave(
        slave_id=1,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
    )
    servo2 = net.connect_to_slave(
        slave_id=2,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
    )
    servo3 = net.connect_to_slave(
        slave_id=3,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
    )

    # All servos should initially have valid references
    assert servo1.slave_exists is True
    assert servo2.slave_exists is True
    assert servo3.slave_exists is True

    # Get initial state of servo1
    initial_state = servo1.slave.state

    # Simulate servo2 and servo3 disappearing by shrinking the network to 1 slave
    pysoem_mock_network.set_num_slaves(1)
    net._EthercatNetwork__init_nodes()

    # servo1 should still exist, but servo2 and servo3 should not
    assert servo1.slave_exists is True
    assert servo2.slave_exists is False
    assert servo3.slave_exists is False

    # _change_nodes_state should handle a list containing non-existent slaves
    # It should skip the non-existent slaves when changing state, but return False
    # because _check_node_state requires ALL nodes to exist and match the target state
    target_state = pysoem.SAFEOP_STATE  # Use a different state than initial
    result = net._change_nodes_state([servo1, servo2, servo3], target_state)

    # servo1's state should be changed to the target state
    assert servo1.slave.state == target_state

    # The method should return False because servo2 and servo3 don't exist
    assert result is False

    # Change state with only the existing servo - should return True
    result = net._change_nodes_state([servo1], pysoem.OP_STATE)
    assert result is True
    assert servo1.slave.state == pysoem.OP_STATE

    # Change servo1 back and test with only non-existent slaves - should return False
    servo1.slave.state = initial_state
    result = net._change_nodes_state([servo2, servo3], pysoem.OP_STATE)
    assert result is False
    # servo1 state should not have changed
    assert servo1.slave.state == initial_state

    # Test with a single non-existent servo - should return False
    result = net._change_nodes_state(servo2, pysoem.OP_STATE)
    assert result is False

    net.close_ecat_master()


def test_disconnect_from_slave_with_non_existent_slave(pysoem_mock_network):
    """Test that disconnect_from_slave works when the slave doesn't exist.

    This verifies that disconnecting a servo whose slave reference has been set to None
    (because the physical slave disappeared) doesn't crash the application.
    """
    # Track disconnect callback invocations
    disconnect_called = []

    def disconnect_callback(servo):
        disconnect_called.append(servo.slave_id)

    net = EthercatNetwork("dummy_ifname")

    # Connect to 2 slaves with disconnect callbacks
    servo1 = net.connect_to_slave(
        slave_id=1,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
        disconnect_callback=disconnect_callback,
    )
    servo2 = net.connect_to_slave(
        slave_id=2,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
        disconnect_callback=disconnect_callback,
    )

    # Both servos should initially have valid references
    assert servo1.slave_exists is True
    assert servo2.slave_exists is True
    assert len(net.servos) == 2

    # Simulate servo2 disappearing by shrinking the network to 1 slave
    pysoem_mock_network.set_num_slaves(1)
    net._EthercatNetwork__init_nodes()

    # servo2 should now have slave_exists = False
    assert servo1.slave_exists is True
    assert servo2.slave_exists is False

    # Disconnect servo2 - should work without crashing even though slave doesn't exist
    net.disconnect_from_slave(servo2)

    # Verify servo2 was removed from the network
    assert len(net.servos) == 1
    assert servo2 not in net.servos
    assert servo1 in net.servos

    # Verify disconnect callback was called for servo2
    assert 2 in disconnect_called

    # Network should still be running because servo1 is still connected
    assert net._EthercatNetwork__is_master_running is True

    # Now disconnect servo1 (which still exists) - should work normally
    net.disconnect_from_slave(servo1)

    # Verify servo1 was removed and network was closed
    assert len(net.servos) == 0
    assert 1 in disconnect_called
    assert net._EthercatNetwork__is_master_running is False


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

    previous_networks = ETHERCAT_NETWORK_REFERENCES.copy()
    net_1 = EthercatNetwork("dummy_network_1", gil_release_config=GilReleaseConfig.always())
    assert set_network_reference_spy.call_count == 1
    assert len(ETHERCAT_NETWORK_REFERENCES) == len(previous_networks) + 1
    assert net_1 in ETHERCAT_NETWORK_REFERENCES

    # Create a second network
    net_2 = EthercatNetwork("dummy_network_2", gil_release_config=GilReleaseConfig.always())
    assert set_network_reference_spy.call_count == 2
    assert len(ETHERCAT_NETWORK_REFERENCES) == len(previous_networks) + 2
    assert net_1 in ETHERCAT_NETWORK_REFERENCES
    assert net_2 in ETHERCAT_NETWORK_REFERENCES

    # Disconnect the first network so that the reference is cleared
    net_1.close_ecat_master()
    assert release_network_reference_spy.call_count == 1
    assert len(ETHERCAT_NETWORK_REFERENCES) == len(previous_networks) + 1

    # Lose the reference to the second network, it should still exist in the stack
    net_2_id = id(net_2)
    net_2 = None
    net_2_id_found = False
    for ref_net in ETHERCAT_NETWORK_REFERENCES:
        if id(ref_net) == net_2_id:
            net_2_id_found = True
            break
    assert net_2_id_found is True
    assert release_network_reference_spy.call_count == 1  # Has not been called again

    release_networks = [net for net in ETHERCAT_NETWORK_REFERENCES if net not in previous_networks]
    for net in release_networks:
        release_network_reference(net)


@pytest.mark.ethercat
def test_master_reference_is_kept_after_scan(setup_descriptor):
    previous_networks = ETHERCAT_NETWORK_REFERENCES.copy()
    net_1 = EthercatNetwork(setup_descriptor.ifname, gil_release_config=GilReleaseConfig.always())
    assert len(ETHERCAT_NETWORK_REFERENCES) == len(previous_networks) + 1
    assert net_1 in ETHERCAT_NETWORK_REFERENCES

    net_1.scan_slaves()

    assert len(ETHERCAT_NETWORK_REFERENCES) == len(previous_networks) + 1
    assert net_1 in ETHERCAT_NETWORK_REFERENCES

    net_1.close_ecat_master()

    assert len(ETHERCAT_NETWORK_REFERENCES) == len(previous_networks)


@pytest.mark.ethercat
def test_network_reference_is_added_back_if_servo_connected_after_close(setup_descriptor):
    previous_networks = ETHERCAT_NETWORK_REFERENCES.copy()
    net = EthercatNetwork(setup_descriptor.ifname, gil_release_config=GilReleaseConfig.always())
    assert len(ETHERCAT_NETWORK_REFERENCES) == len(previous_networks) + 1
    assert net in ETHERCAT_NETWORK_REFERENCES

    assert len(net.servos) == 0
    servo = net.connect_to_slave(
        setup_descriptor.slave,
        setup_descriptor.dictionary.as_posix(),
    )
    assert len(net.servos) == 1

    net.disconnect_from_slave(servo)
    assert len(net.servos) == 0
    assert len(ETHERCAT_NETWORK_REFERENCES) == len(previous_networks)

    # Connect again to a servo, the network reference should be added back
    servo = net.connect_to_slave(
        setup_descriptor.slave,
        setup_descriptor.dictionary.as_posix(),
    )
    assert len(net.servos) == 1

    assert len(ETHERCAT_NETWORK_REFERENCES) == len(previous_networks) + 1
    assert net in ETHERCAT_NETWORK_REFERENCES

    net.disconnect_from_slave(servo)


@pytest.mark.ethercat
def test_network_is_not_released_if_gil_operation_ongoing(mocker, setup_descriptor):
    blocking_time = 5

    def dummy_config_init(usetable=False, *, release_gil=None):  # noqa: ARG001
        start_time = time.time()
        while time.time() - start_time < blocking_time:
            time.sleep(0.01)

    def thread_scan_slaves(network, event):
        if not event.is_set():  # Run a single time
            network.scan_slaves()
            event.set()

    def thread_close_master(network, event):
        event.wait()
        network.close_ecat_master()

    mocker.patch.object(pysoem.Master, "config_init", dummy_config_init)

    previous_networks = ETHERCAT_NETWORK_REFERENCES.copy()
    network = EthercatNetwork(setup_descriptor.ifname, gil_release_config=GilReleaseConfig.always())
    assert len(ETHERCAT_NETWORK_REFERENCES) == len(previous_networks) + 1
    assert network in ETHERCAT_NETWORK_REFERENCES

    event = threading.Event()

    thread_block_lock = threading.Thread(target=thread_scan_slaves, args=(network, event))
    thread_acquire_lock = threading.Thread(target=thread_close_master, args=(network, event))

    thread_block_lock_start_time = time.time()
    thread_block_lock.start()
    time.sleep(0.05)  # wait for the thread to start
    assert network._lock.locked() is True

    thread_acquire_lock.start()

    # The thread is locked, so the second thread should wait until the first finishes
    while network in ETHERCAT_NETWORK_REFERENCES:
        time.sleep(0.05)
    assert np.isclose(time.time() - thread_block_lock_start_time, blocking_time, atol=0.5)

    thread_block_lock.join()
    thread_acquire_lock.join()
    assert len(ETHERCAT_NETWORK_REFERENCES) == len(previous_networks)


def test_slave_update_on_config_init(pysoem_mock_network):  # noqa: ARG001
    net = EthercatNetwork("dummy_ifname")

    servo = net.connect_to_slave(
        slave_id=1,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
    )

    assert len(net.servos) == 1
    assert net.servos[0] == servo
    original_slave = servo.slave
    # The slave contains the emergency callbacks
    assert original_slave._emcy_callbacks[0] == servo._on_emcy

    # Now, a method could __init_nodes, which re-creates the pysoem slaves
    net._EthercatNetwork__init_nodes()
    assert len(net.servos) == 1
    # The slave should be updated
    assert servo.slave is not original_slave
    # And the emergency callback retained
    assert original_slave._emcy_callbacks[0] == servo._on_emcy


def test_slave_reference_set_to_none_when_not_in_init_nodes(pysoem_mock_network):
    """Test that servo's slave reference is set to None when slave_id is not in __last_init_nodes.

    This verifies the fix for INGK-1211 where missing slaves after config_init
    should have their slave references set to None.
    """
    net = EthercatNetwork("dummy_ifname")

    # Connect to slaves 1, 2, and 3 (default is 3 slaves)
    servo1 = net.connect_to_slave(
        slave_id=1,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
    )
    servo2 = net.connect_to_slave(
        slave_id=2,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
    )
    servo3 = net.connect_to_slave(
        slave_id=3,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
    )

    assert len(net.servos) == 3
    assert servo1.slave_exists is True
    assert servo2.slave_exists is True
    assert servo3.slave_exists is True

    # Simulate the network shrinking to only 1 slave
    # This simulates slaves 2 and 3 being physically disconnected
    pysoem_mock_network.set_num_slaves(1)
    net._EthercatNetwork__init_nodes()

    # Servo 1 should still have a valid reference (it's still present)
    assert servo1.slave_exists is True
    assert servo1.slave.id == 1

    # Servos 2 and 3 should have None references (they disappeared)
    assert servo2.slave_exists is False
    assert servo3.slave_exists is False

    net.close_ecat_master()


def test_net_status_listener_handles_none_slave_reference(pysoem_mock_network, mocker):  # noqa: ARG001
    """Test that NetStatusListener doesn't crash when servo.slave is None.

    This verifies the fix for INGK-1211 where the listener checks slave_exists
    before accessing servo.slave.state.
    """
    net = EthercatNetwork("dummy_ifname")

    servo = net.connect_to_slave(
        slave_id=1,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
    )

    # Verify initial state
    assert net.get_servo_state(1) == NetState.CONNECTED
    assert servo.slave_exists is True

    # Start the status listener to initialize __listener_net_status
    net.start_status_listener()

    # Manually set the slave reference to None to simulate a missing slave
    servo.update_slave_reference(None)

    # Manually trigger the listener's process method to detect the missing slave
    net._EthercatNetwork__listener_net_status.process()

    # The listener should have detected the None reference and set state to DISCONNECTED
    assert servo.slave_exists is False
    assert net.get_servo_state(1) == NetState.DISCONNECTED, (
        "NetStatusListener should detect None slave reference and set state to DISCONNECTED"
    )

    net.stop_status_listener()
    net.close_ecat_master()


def test_net_status_listener_detects_slave_removal(pysoem_mock_network, mocker):  # noqa: ARG001
    """Test that NetStatusListener properly detects when a slave is removed.

    This verifies the complete flow: slave disappears -> config_init sets reference to None
    -> listener detects removal.
    """
    # Track callback invocations
    removal_detected = threading.Event()

    def status_callback(event: NetDevEvt):
        if event == NetDevEvt.REMOVED:
            removal_detected.set()

    net = EthercatNetwork("dummy_ifname")

    servo = net.connect_to_slave(
        slave_id=1,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
    )

    # Subscribe to status changes
    net.subscribe_to_status(1, status_callback)

    # Start the status listener to initialize __listener_net_status
    net.start_status_listener()

    # Verify initial state
    assert net.get_servo_state(1) == NetState.CONNECTED
    assert servo.slave_exists is True

    # Simulate slave removal by setting reference to None
    servo.update_slave_reference(None)

    # Manually trigger the listener's process method to detect the removal
    net._EthercatNetwork__listener_net_status.process()

    # The listener should have detected the removal and called the callback
    assert removal_detected.is_set(), "NetStatusListener should detect slave removal"
    assert net.get_servo_state(1) == NetState.DISCONNECTED

    net.stop_status_listener()
    net.close_ecat_master()


def test_net_status_listener_detects_slave_reconnection(pysoem_mock_network, mocker):
    """Test that NetStatusListener properly detects when a slave reconnects.

    This verifies the complete flow: slave reappears -> config_init updates reference
    -> listener detects reconnection.
    """
    # Track callback invocations
    events_detected = []

    def status_callback(event: NetDevEvt):
        events_detected.append(event)

    # Mock _recover_from_disconnection to return True
    mocker.patch.object(EthercatNetwork, "_recover_from_disconnection", return_value=True)

    net = EthercatNetwork("dummy_ifname")

    net.connect_to_slave(
        slave_id=1,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
    )

    # Subscribe to status changes
    net.subscribe_to_status(1, status_callback)

    # Start the status listener to initialize __listener_net_status
    net.start_status_listener()

    # Verify initial state
    assert net.get_servo_state(1) == NetState.CONNECTED

    # Simulate slave removal by shrinking the network to 0 slaves
    pysoem_mock_network.set_num_slaves(0)
    net._EthercatNetwork__init_nodes()

    # Manually trigger the listener's process method to detect removal
    net._EthercatNetwork__listener_net_status.process()

    assert NetDevEvt.REMOVED in events_detected
    assert net.get_servo_state(1) == NetState.DISCONNECTED

    # Simulate slave reconnection by expanding the network back to 1 slave
    pysoem_mock_network.set_num_slaves(1)
    net._EthercatNetwork__init_nodes()

    # Manually trigger the listener's process method to detect reconnection
    net._EthercatNetwork__listener_net_status.process()

    # The listener should have detected the reconnection
    assert NetDevEvt.ADDED in events_detected
    assert net.get_servo_state(1) == NetState.CONNECTED

    net.stop_status_listener()
    net.close_ecat_master()


@pytest.mark.ethercat
def test_slave_is_in_preop_state_if_exception_in_pdo_thread(
    net: "EthercatNetwork", servo: "EthercatServo", mocker: "MockerFixture"
) -> None:
    rpdo_map: RPDOMap = RPDOMap()
    tpdo_map: TPDOMap = TPDOMap()
    initial_operation_mode: int = cast("int", servo.read("DRV_OP_CMD"))
    operation_mode = PDOMap.create_item_from_register_uid(
        "DRV_OP_CMD", dictionary=servo.dictionary, value=initial_operation_mode, axis=1
    )
    actual_position = PDOMap.create_item_from_register_uid(
        "CL_POS_FBK_VALUE", dictionary=servo.dictionary, axis=1
    )
    rpdo_map.add_item(operation_mode)
    tpdo_map.add_item(actual_position)
    servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
    pdo_map_items = (operation_mode, actual_position)
    # Choose a random operation mode: [voltage, current, velocity, position]
    random_op_mode = random.choice([
        op_mode for op_mode in [0x00, 0x02, 0x03, 0x04] if op_mode != initial_operation_mode
    ])
    initial_operation_mode = initial_operation_mode
    rpdo_value = random_op_mode

    def send_callback() -> None:
        rpdo_map_item, _ = pdo_map_items
        rpdo_map_item.value = rpdo_value  # type: ignore[misc]

    def receive_callback() -> None:
        return

    rpdo_map.subscribe_to_process_data_event(send_callback)
    tpdo_map.subscribe_to_process_data_event(receive_callback)

    def mock_send_receive_processdata(*args, **kwargs) -> None:  # type: ignore [no-untyped-def]  # noqa: ARG001
        raise RuntimeError("Test error in PDO thread")

    refresh_rate: float = 0.5
    net.activate_pdos(refresh_rate=refresh_rate)
    time.sleep(2 * refresh_rate)
    assert net._EthercatNetwork__exceptions_in_thread == 0

    # Mock to raise an exception
    mocker.patch.object(
        EthercatNetwork,
        "send_receive_processdata",
        side_effect=mock_send_receive_processdata,
    )
    time.sleep(4 * refresh_rate)
    assert net._EthercatNetwork__exceptions_in_thread > 0

    # Net should restore servos to PREOP state
    assert servo.slave is not None
    assert servo.slave.state is pysoem.PREOP_STATE
