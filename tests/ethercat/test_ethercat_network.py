import contextlib
from unittest.mock import MagicMock, PropertyMock, call

import tests.resources

with contextlib.suppress(ImportError):
    import pysoem
import random
import threading
import time
from collections.abc import Generator
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
    set_network_reference,
)
from ingenialink.exceptions import ILError, ILFirmwareLoadError
from ingenialink.network import NetDevEvt, NetState
from ingenialink.pdo import PDOMap, RPDOMap, TPDOMap
from tests.ethercat.mock import pysoem_mock_network

if TYPE_CHECKING:
    from pytest import FixtureRequest
    from pytest_mock import MockerFixture
    from summit_testing_framework.environment import Environment
    from summit_testing_framework.setup_fixtures import ConnectionWrapper
    from summit_testing_framework.setups.descriptors import DriveEcatSetup

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
    with net.running():
        yield net, mock_slave


@pytest.mark.no_pcap
def test_raise_exception_if_not_winpcap():
    try:
        import pysoem  # noqa: F401,PLC0415

        pytest.fail("WinPcap appears to be installed and thus the test cannot be executed.")
    except ImportError:
        pass
    previous_networks = ETHERCAT_NETWORK_REFERENCES.copy()
    with pytest.raises(ImportError):
        EthercatNetwork("dummy_ifname")
    release_networks = [net for net in ETHERCAT_NETWORK_REFERENCES if net not in previous_networks]
    for net in release_networks:
        release_network_reference(net)


@pytest.mark.pcap
def test_load_firmware_file_not_found_error():
    net = EthercatNetwork("fake_interface")
    with pytest.raises(FileNotFoundError):
        net.load_firmware("ethercat.sfu", True)
    net.close_ecat_master()


@pytest.mark.pcap
def test_load_firmware_no_slave_detected_error(mocked_network_for_firmware_loading):
    net, _ = mocked_network_for_firmware_loading
    slave_id = 23
    with pytest.raises(
        ILError,
        match=f"Slave {slave_id} was not found.",
    ):
        net.load_firmware("dummy_file.lfu", False, slave_id=slave_id)


@pytest.mark.ethercat
def test_find_adapters(setup_descriptor: "DriveEcatSetup") -> None:
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


@pytest.mark.pcap
def test_load_firmware_boot_state_failure(
    mocker: "MockerFixture", mocked_network_for_firmware_loading
):
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


@pytest.mark.pcap
def test_load_firmware_foe_write_failure(
    mocker: "MockerFixture", mocked_network_for_firmware_loading
):
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


@pytest.mark.pcap
def test_load_firmware_success_after_retry(
    mocker: "MockerFixture", mocked_network_for_firmware_loading
):
    net, slave = mocked_network_for_firmware_loading
    mocker.patch.object(net, "_switch_to_boot_state", side_effect=[False, True])
    mocker.patch.object(net, "_write_foe", return_value=1)
    mocker.patch("time.sleep", return_value=None)
    slave.state_check.return_value = pysoem.PREOP_STATE
    net.load_firmware("dummy_file.sfu", False, slave_id=1)


@pytest.mark.pcap
def test_wrong_interface_name_error():
    net = EthercatNetwork("fake_interface")
    slave_id = 1
    dictionary = "fake_dictionary.xdf"
    with pytest.raises(ConnectionError):
        net.connect_to_slave(slave_id, dictionary)
    net.close_ecat_master()


@pytest.mark.ethercat
@pytest.mark.parametrize("slave_id", [-1, "one", None])
def test_connect_to_slave_invalid_id(
    net: "EthercatNetwork",
    servo_with_reconnect: "ConnectionWrapper",
    setup_descriptor: "DriveEcatSetup",
    slave_id,
) -> None:
    servo_with_reconnect.disconnect()
    with pytest.raises(ValueError):
        net.connect_to_slave(slave_id, setup_descriptor.dictionary)


@pytest.mark.ethercat
def test_connect_to_no_detected_slave(
    net: "EthercatNetwork",
    setup_descriptor: "DriveEcatSetup",
    servo_with_reconnect: "ConnectionWrapper",
) -> None:
    servo_with_reconnect.disconnect()
    assert servo_with_reconnect.is_connected() is False

    slaves = net.scan_slaves()
    slave_id = slaves[-1] + 1

    with pytest.raises(ILError):
        net.connect_to_slave(slave_id, setup_descriptor.dictionary)


@pytest.mark.ethercat
def test_connect_to_slave_with_callback(
    setup_descriptor: "DriveEcatSetup",
    net: "EthercatNetwork",
    servo_with_reconnect: "ConnectionWrapper",
) -> None:
    servo_with_reconnect.disconnect()

    disconnected_servos = []

    def dummy_callback(servo):
        disconnected_servos.append(servo.slave_id)

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
def test_scan_slaves_raises_exception_if_drive_is_already_connected(
    servo: "EthercatServo", net: "EthercatNetwork"
) -> None:
    net._ecat_master.read_state()
    assert servo.slave.state_check(pysoem.PREOP_STATE) == pysoem.PREOP_STATE
    with pytest.raises(ILError):
        net.scan_slaves()
    assert servo.slave.state_check(pysoem.PREOP_STATE) == pysoem.PREOP_STATE


@pytest.mark.ethercat
def test_scan_slaves_info(
    setup_specifier,
    servo_with_reconnect: "ConnectionWrapper",
    setup_descriptor: "DriveEcatSetup",
    request: "FixtureRequest",
) -> None:
    servo_with_reconnect.disconnect()
    net = servo_with_reconnect.get_net()
    slaves_info = net.scan_slaves_info()

    assert len(slaves_info) > 0
    assert setup_descriptor.slave in slaves_info

    if isinstance(setup_specifier, (RackServiceConfigSpecifier, MultiRackServiceConfigSpecifier)):
        drive = request.getfixturevalue("get_drive_configuration_from_rack_service")
        assert slaves_info[setup_descriptor.slave].product_code == drive.product_code


@pytest.mark.ethercat
def test_update_sdo_timeout(net: "EthercatNetwork") -> None:
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
def test_update_pysoem_timeouts(net: "EthercatNetwork") -> None:
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
def test_check_node_state(servo: "EthercatServo", net: "EthercatNetwork") -> None:
    # True when list is not empty
    assert net._check_node_state(servo, pysoem.PREOP_STATE)
    # False when list is not empty
    assert not net._check_node_state([], pysoem.PREOP_STATE)


@pytest.mark.pcap
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


@pytest.mark.pcap
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


@pytest.mark.pcap
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


@pytest.mark.pcap
def test_stop_pdos_skips_disconnected_slaves(pysoem_mock_network, mocker):  # noqa: ARG001
    """Test that stop_pdos() skips slaves in NONE_STATE and does not call __init_nodes().

    When a slave is physically disconnected, its state transitions to NONE_STATE.
    stop_pdos() must not attempt to change state or call __init_nodes() for such slaves —
    doing so would clear slave references and prevent reconnection detection.
    """
    net = EthercatNetwork("dummy_ifname")
    servo = net.connect_to_slave(
        slave_id=1,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
    )
    assert servo.slave_exists is True

    # Simulate disconnection: slave transitions to NONE_STATE
    servo.slave.state = pysoem.NONE_STATE

    init_nodes_mock = mocker.patch.object(net, "_EthercatNetwork__init_nodes")
    net.stop_pdos()

    init_nodes_mock.assert_not_called()
    net.close_ecat_master()


@pytest.mark.pcap
@pytest.mark.usefixtures(pysoem_mock_network.__name__)
def test_recover_from_disconnection_does_not_shortcut_when_slave_ref_cleared():
    """Test that recover_from_disconnection() does not return True when a slave ref is missing.

    The master can report PREOP_STATE while a slave reference has been cleared by a
    previous failed config_init(). Without the fix, the PREOP shortcut would return True
    (false positive), leading to a bounce loop when the reconnect task fails.
    """
    net = EthercatNetwork("dummy_ifname")
    servo = net.connect_to_slave(
        slave_id=1,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
    )
    assert servo.slave_exists is True

    # Simulate a previous failed config_init(): slave reference is cleared
    servo.update_slave_reference(None)
    assert servo.slave_exists is False

    # Master reports PREOP state (the shortcut path)
    net._ecat_master.state = pysoem.PREOP_STATE

    # Should NOT return True — slave refs are invalid despite master being in PREOP
    assert net.recover_from_disconnection() is False

    net.close_ecat_master()


@pytest.mark.pcap
@pytest.mark.usefixtures(pysoem_mock_network.__name__)
def test_recover_from_disconnection_closes_and_reopens_master(
    mocker,
):
    """Test that recover_from_disconnection() closes and reopens the SOEM master before re-enum.

    After a cable disconnect the SOEM master's internal state can become corrupted.
    Closing and reopening the master reinitialises the NIC socket so that config_init()
    can discover slaves again.
    """
    net = EthercatNetwork("dummy_ifname")
    net.connect_to_slave(
        slave_id=1,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
    )

    close_mock = mocker.patch.object(net._ecat_master, "close")
    open_mock = mocker.patch.object(net._ecat_master, "open")
    manager = MagicMock()
    manager.attach_mock(close_mock, "close")
    manager.attach_mock(open_mock, "open")

    # Master state is INIT (not PREOP) so the shortcut does not trigger.
    net.recover_from_disconnection()

    manager.assert_has_calls([call.close(), call.open(net.interface_name)], any_order=False)

    net.close_ecat_master()


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
def test_master_reference_is_kept_while_network_is_alive(mocker) -> None:
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
def test_master_reference_is_not_kept_after_scan(
    setup_descriptor: "DriveEcatSetup",
    servo_with_reconnect: "ConnectionWrapper",
    mocker: "MockerFixture",
) -> None:
    """Scan slaves should use the network context, so the reference is not kept after the call."""
    servo_with_reconnect.disconnect()
    previous_networks = ETHERCAT_NETWORK_REFERENCES.copy()
    net_1 = EthercatNetwork(setup_descriptor.ifname, gil_release_config=GilReleaseConfig.always())
    assert len(ETHERCAT_NETWORK_REFERENCES) == len(previous_networks) + 1
    assert net_1 in ETHERCAT_NETWORK_REFERENCES

    # Spy on the actual methods that context manager calls to verify behavior
    start_master_spy = mocker.spy(net_1, "_start_master")
    close_master_spy = mocker.spy(net_1, "close_ecat_master")

    slaves = net_1.scan_slaves()

    # Verify context manager behavior: master was started and then closed
    assert start_master_spy.call_count == 1, (
        "Context manager should start master during scan_slaves"
    )
    assert close_master_spy.call_count == 1, "Context manager should close master after scan_slaves"

    # Verify we got the slave list before the context closed
    assert len(slaves) > 0, "Should have detected slaves"

    # Reference should NOT be present after scan - context started and stopped the master,
    # so it released the reference on exit
    assert len(ETHERCAT_NETWORK_REFERENCES) == len(previous_networks)
    assert net_1 not in ETHERCAT_NETWORK_REFERENCES
    assert net_1._EthercatNetwork__is_master_running is False


@pytest.mark.ethercat
def test_network_reference_is_added_back_if_servo_connected_after_close(
    setup_descriptor: "DriveEcatSetup", servo_with_reconnect: "ConnectionWrapper"
) -> None:
    servo_with_reconnect.disconnect()

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
def test_network_is_not_released_if_gil_operation_ongoing(
    mocker: "MockerFixture", setup_descriptor: "DriveEcatSetup"
) -> None:
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


@pytest.mark.pcap
@pytest.mark.usefixtures(pysoem_mock_network.__name__)
def test_slave_update_on_config_init():
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


@pytest.mark.pcap
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


@pytest.mark.pcap
@pytest.mark.usefixtures(pysoem_mock_network.__name__)
def test_net_status_listener_handles_none_slave_reference(mocker):
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

    # Prevent recovery from restoring the slave reference so we can assert
    # that detection alone sets the state correctly.
    mocker.patch.object(EthercatNetwork, "recover_from_disconnection", return_value=False)

    # Manually trigger the listener's process method to detect the missing slave
    net._EthercatNetwork__listener_net_status.process()

    # The listener should have detected the None reference and set state to DISCONNECTED
    assert servo.slave_exists is False
    assert net.get_servo_state(1) == NetState.DISCONNECTED, (
        "NetStatusListener should detect None slave reference and set state to DISCONNECTED"
    )

    net.stop_status_listener()
    net.close_ecat_master()


@pytest.mark.pcap
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


@pytest.mark.pcap
def test_net_status_listener_detects_slave_reconnection(pysoem_mock_network, mocker):
    """Test that NetStatusListener properly detects when a slave reconnects.

    This verifies the complete flow: slave reappears -> config_init updates reference
    -> listener detects reconnection.
    """
    # Track callback invocations
    events_detected = []

    def status_callback(event: NetDevEvt):
        events_detected.append(event)

    # Mock recover_from_disconnection to return True
    mocker.patch.object(EthercatNetwork, "recover_from_disconnection", return_value=True)

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


@pytest.mark.pcap
@pytest.mark.usefixtures(pysoem_mock_network.__name__)
def test_net_status_listener_retries_recovery_after_failed_attempt(
    mocker,
):
    """Test that process() retries recovery even when slave_exists=False after a failed attempt.

    After a failed recover_from_disconnection(), config_init() may clear slave references
    (slave_exists=False). The fix ensures recovery is retried based on servo_state==DISCONNECTED
    rather than is_servo_alive, so the slave can be rediscovered on the next process() cycle.
    """
    events_detected = []

    def status_callback(event: NetDevEvt) -> None:
        events_detected.append(event)

    net = EthercatNetwork("dummy_ifname")
    servo = net.connect_to_slave(
        slave_id=1,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
    )
    net.subscribe_to_status(1, status_callback)
    net.start_status_listener()

    # Simulate disconnection with cleared slave reference (as left by a failed config_init)
    saved_slave = servo.slave
    servo.update_slave_reference(None)
    net._set_servo_state(1, NetState.DISCONNECTED)

    call_count = [0]

    def recover_side_effect() -> bool:
        call_count[0] += 1
        if call_count[0] >= 2:
            # Cable reconnected: restore slave reference
            servo.update_slave_reference(saved_slave)
            servo.slave.state = pysoem.PREOP_STATE
            return True
        return False

    mocker.patch.object(
        EthercatNetwork, "recover_from_disconnection", side_effect=recover_side_effect
    )

    # First process: recovery fails, ADDED should not be emitted
    net._EthercatNetwork__listener_net_status.process()
    assert NetDevEvt.ADDED not in events_detected
    assert net.get_servo_state(1) == NetState.DISCONNECTED

    # Second process: recovery succeeds (cable reconnected), ADDED should be emitted
    net._EthercatNetwork__listener_net_status.process()
    assert NetDevEvt.ADDED in events_detected
    assert net.get_servo_state(1) == NetState.CONNECTED

    net.stop_status_listener()
    net.close_ecat_master()


@pytest.mark.pcap
def test_net_status_listener_recovery_called_once_for_multiple_disconnected_slaves(
    pysoem_mock_network,
    mocker,  # noqa: ARG001
):
    """Test that recover_from_disconnection() is called once even with multiple disconnected slaves.

    recover_from_disconnection() is a network-wide operation. Calling it per-slave in a loop
    causes redundant config_init() runs and delays. The fix calls it once then verifies
    each slave individually (Phase 4).
    """
    net = EthercatNetwork("dummy_ifname")
    pysoem_mock_network.set_num_slaves(2)

    servo1 = net.connect_to_slave(
        slave_id=1,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
    )
    servo2 = net.connect_to_slave(
        slave_id=2,
        dictionary=tests.resources.DEN_NET_E_2_8_0_xdf_v3,
    )
    net.subscribe_to_status(1, lambda _: None)
    net.subscribe_to_status(2, lambda _: None)
    net.start_status_listener()

    # Put both slaves in DISCONNECTED state while keeping slave refs valid
    net._set_servo_state(1, NetState.DISCONNECTED)
    net._set_servo_state(2, NetState.DISCONNECTED)
    servo1.slave.state = pysoem.PREOP_STATE
    servo2.slave.state = pysoem.PREOP_STATE

    recover_mock = mocker.patch.object(
        EthercatNetwork, "recover_from_disconnection", return_value=True
    )

    net._EthercatNetwork__listener_net_status.process()

    recover_mock.assert_called_once()
    assert net.get_servo_state(1) == NetState.CONNECTED
    assert net.get_servo_state(2) == NetState.CONNECTED

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


@pytest.mark.ethercat
def test_recover_from_disconnection(net: "EthercatNetwork", servo: "EthercatServo", caplog) -> None:
    """Test that recover_from_disconnection properly rediscovers slaves after disconnection.

    This test uses a real EtherCAT drive and simulates a disconnection scenario by setting
    the slave reference to None. The recover_from_disconnection method should call
    __init_nodes() to rediscover the physical drive and restore communication.
    """
    # Verify initial state - servo is connected and in PREOP state
    assert servo.slave_exists is True
    assert servo.slave.state == pysoem.PREOP_STATE, "Servo should be in PREOP state initially"

    # Verify that recover_from_disconnection returns True when servo is properly connected
    assert net.recover_from_disconnection() is True

    # Simulate slave disconnection by changing state to INIT
    net._change_nodes_state(servo, pysoem.INIT_STATE)
    assert servo.slave.state == pysoem.INIT_STATE, (
        "Servo should be in INIT state after disconnection"
    )
    caplog.clear()
    with caplog.at_level("WARNING"):
        result = net.recover_from_disconnection()
        assert result is True, "recover_from_disconnection should rediscover the physical slave"
        assert "CoE communication recovered." in caplog.text, "Should log recovery success message"

    assert servo.slave.state == pysoem.PREOP_STATE, "Servo should be in PREOP state after recovery"


@pytest.mark.ethercat
def test_net_status_listener_detects_power_cycle(
    net: "EthercatNetwork", servo: "EthercatServo", environment: "Environment"
) -> None:
    """Test that NetStatusListener detects disconnection and reconnection on a real power cycle,
    both with PDOs inactive and with PDOs actively running.

    Scenario 1 (no PDOs): verifies the basic listener detect-and-recover path.
    Scenario 2 (PDOs active): verifies that when a WKC error stops the PDO thread, the listener
    resumes calling process() and completes the same detect-and-recover cycle, leaving PDOs
    stopped after reconnection.
    """
    removed_event = threading.Event()
    added_event = threading.Event()

    def status_callback(evt: NetDevEvt) -> None:
        if evt == NetDevEvt.REMOVED:
            removed_event.set()
        elif evt == NetDevEvt.ADDED:
            added_event.set()

    net.subscribe_to_status(servo.slave_id, status_callback)
    net.start_status_listener()

    try:
        # --- Scenario 1: power cycle without PDOs active ---
        environment.power_cycle(wait_for_drives=False, reconnect_drives=False)

        assert removed_event.wait(timeout=30.0), (
            "NetStatusListener did not detect the drive disconnection within 30 s"
        )
        assert net.get_servo_state(servo.slave_id) == NetState.DISCONNECTED

        assert added_event.wait(timeout=60.0), (
            "NetStatusListener did not detect the drive reconnection within 60 s"
        )
        assert net.get_servo_state(servo.slave_id) == NetState.CONNECTED

        # --- Scenario 2: power cycle with PDOs active ---
        removed_event.clear()
        added_event.clear()

        rpdo_map = RPDOMap()
        tpdo_map = TPDOMap()
        initial_operation_mode = cast("int", servo.read("DRV_OP_CMD"))
        operation_mode = PDOMap.create_item_from_register_uid(
            "DRV_OP_CMD", dictionary=servo.dictionary, value=initial_operation_mode, axis=1
        )
        actual_position = PDOMap.create_item_from_register_uid(
            "CL_POS_FBK_VALUE", dictionary=servo.dictionary, axis=1
        )
        rpdo_map.add_item(operation_mode)
        tpdo_map.add_item(actual_position)
        servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])

        rpdo_map.subscribe_to_process_data_event(lambda: None)
        tpdo_map.subscribe_to_process_data_event(lambda: None)

        refresh_rate: float = 0.5
        net.activate_pdos(refresh_rate=refresh_rate)
        time.sleep(2 * refresh_rate)
        assert net.pdo_manager.is_active is True

        # Power cycle while PDOs are running. The PDO thread detects the WKC error and stops
        # PDOs via the exception handler, after which the listener resumes calling process().
        environment.power_cycle(wait_for_drives=False, reconnect_drives=False)

        assert removed_event.wait(timeout=30.0), (
            "NetStatusListener did not detect the drive disconnection within 30 s (PDO scenario)"
        )
        assert net.get_servo_state(servo.slave_id) == NetState.DISCONNECTED

        assert added_event.wait(timeout=60.0), (
            "NetStatusListener did not detect the drive reconnection within 60 s (PDO scenario)"
        )
        assert net.get_servo_state(servo.slave_id) == NetState.CONNECTED
        assert net.pdo_manager.is_active is False, (
            "PDOs should have been stopped by the exception handler during power cycle"
        )
    finally:
        # servo/net status listeners are not reset
        # https://novantamotion.atlassian.net/browse/CIT-627
        net.stop_status_listener()


@pytest.mark.pcap
def test_ensure_network_reference_method():
    """Test the _ensure_network_reference helper method.

    If the network is not in ETHERCAT_NETWORK_REFERENCES, calling this method
    should add it back. If it is already present, calling the method should have no effect.
    """
    net = EthercatNetwork("fake_interface")

    # Remove from references
    if net in ETHERCAT_NETWORK_REFERENCES:
        ETHERCAT_NETWORK_REFERENCES.remove(net)

    assert net not in ETHERCAT_NETWORK_REFERENCES

    # Call the method
    net._EthercatNetwork__ensure_network_reference()

    assert net in ETHERCAT_NETWORK_REFERENCES

    # Call again - should not duplicate
    previous_count = len(ETHERCAT_NETWORK_REFERENCES)
    net._EthercatNetwork__ensure_network_reference()
    assert net in ETHERCAT_NETWORK_REFERENCES
    assert len(ETHERCAT_NETWORK_REFERENCES) == previous_count

    # Cleanup
    release_network_reference(net)


@pytest.mark.pcap
@pytest.mark.usefixtures(pysoem_mock_network.__name__)
def test_net_status_listener_skips_process_when_pdos_active(mocker):
    """Test that the listener does not call process() while PDOs are running.

    NetStatusListener checks network.pdo_manager.is_active at the top of its run
    loop.  When PDOs are active, process() must not be called to prevent concurrent
    SOEM-master access from the PDO thread and the listener thread.
    """
    net = EthercatNetwork("dummy_ifname")
    net.connect_to_slave(1, tests.resources.DEN_NET_E_2_8_0_xdf_v3)

    # Patch is_active=True BEFORE starting the listener so that the run loop never
    # sees is_active=False and therefore never calls process().
    mocker.patch.object(
        type(net.pdo_manager), "is_active", new_callable=PropertyMock, return_value=True
    )

    net.start_status_listener()
    listener = net._EthercatNetwork__listener_net_status
    listener._NetStatusListener__refresh_time = 0.01  # speed up the run loop
    process_mock = mocker.patch.object(listener, "process")

    time.sleep(0.1)  # allow several run-loop iterations

    process_mock.assert_not_called()

    net.stop_status_listener()
    net.close_ecat_master()


@pytest.mark.pcap
@pytest.mark.usefixtures(pysoem_mock_network.__name__)
def test_net_status_listener_calls_process_when_pdos_inactive(mocker):
    """Test that the listener calls process() normally when PDOs are not running."""
    net = EthercatNetwork("dummy_ifname")
    net.connect_to_slave(1, tests.resources.DEN_NET_E_2_8_0_xdf_v3)

    mocker.patch.object(EthercatNetwork, "recover_from_disconnection", return_value=False)
    net.start_status_listener()
    listener = net._EthercatNetwork__listener_net_status
    listener._NetStatusListener__refresh_time = 0.01  # speed up the run loop

    process_mock = mocker.patch.object(listener, "process")

    time.sleep(0.5)

    assert process_mock.call_count > 0, "process() should be called when PDOs are inactive"

    net.stop_status_listener()
    net.close_ecat_master()


@pytest.mark.pcap
def test_net_status_listener_threaded_disconnect_reconnect_cycle(pysoem_mock_network, mocker):
    """Integration test: the listener *thread* detects a full disconnect/reconnect cycle.

    Unlike the process()-direct tests, this runs the NetStatusListener as an actual thread
    and verifies that REMOVED and ADDED events fire asynchronously using threading.Events.

    The environment controller (pysoem_mock_network) is used to simulate slave
    presence: set_num_slaves(0) makes config_init return no slaves, set_num_slaves(1)
    restores them.  recover_from_disconnection() is mocked to call __init_nodes() at
    the right moment and signal success, keeping the test self-contained.
    """
    removed_event = threading.Event()
    added_event = threading.Event()

    def status_callback(evt: NetDevEvt) -> None:
        if evt == NetDevEvt.REMOVED:
            removed_event.set()
        elif evt == NetDevEvt.ADDED:
            added_event.set()

    net = EthercatNetwork("dummy_ifname")
    servo = net.connect_to_slave(1, tests.resources.DEN_NET_E_2_8_0_xdf_v3)
    net.subscribe_to_status(1, status_callback)
    net.start_status_listener()
    listener = net._EthercatNetwork__listener_net_status
    listener._NetStatusListener__refresh_time = 0.01  # speed up the run loop

    # --- Phase 1: simulate disconnection ---
    # Clearing the slave reference makes is_servo_alive=False on the next process() call.
    servo.update_slave_reference(None)

    assert removed_event.wait(timeout=2.0), "Timeout waiting for REMOVED event"
    assert net.get_servo_state(1) == NetState.DISCONNECTED

    # --- Phase 2: simulate reconnection ---
    # restore the slave reference so that Phase 4 of process() sees a live slave.
    def mock_recovery() -> bool:
        pysoem_mock_network.set_num_slaves(1)
        net._EthercatNetwork__init_nodes()  # slave ref restored; slave.state = INIT_STATE (1)
        return True

    mocker.patch.object(EthercatNetwork, "recover_from_disconnection", side_effect=mock_recovery)

    assert added_event.wait(timeout=2.0), "Timeout waiting for ADDED event"
    assert net.get_servo_state(1) == NetState.CONNECTED

    net.stop_status_listener()
    net.close_ecat_master()


class TestEthercatNetworkContextManager:
    """Tests for the EthercatNetwork context manager functionality."""

    @pytest.fixture
    def net_mocker(self, mocker) -> Generator[EthercatNetwork, None, None]:
        net = EthercatNetwork("fake_interface")
        mocker.patch.object(net, "_start_master")
        mocker.patch.object(net, "close_ecat_master")

        yield net

        if net in ETHERCAT_NETWORK_REFERENCES:
            release_network_reference(network=net)

    @pytest.mark.pcap
    def test_context_manager_starts_and_stops_master(self, net_mocker: "EthercatNetwork") -> None:
        """Test that context manager starts master if not running and closes it on exit."""
        assert net_mocker._EthercatNetwork__is_master_running is False

        with net_mocker.running():
            net_mocker._start_master.assert_called_once()
            # Simulate master running
            net_mocker._EthercatNetwork__is_master_running = True

        net_mocker.close_ecat_master.assert_called_once_with(release_reference=True)

    @pytest.mark.pcap
    def test_context_manager_does_not_close_already_running_master(
        self, net_mocker: "EthercatNetwork"
    ) -> None:
        """Test that context manager doesn't close master that was already running."""

        # Simulate master already running
        net_mocker._EthercatNetwork__is_master_running = True

        with net_mocker.running():
            net_mocker._start_master.assert_not_called()

        net_mocker.close_ecat_master.assert_not_called()

    @pytest.mark.pcap
    def test_context_manager_ensures_network_reference(self, net_mocker: "EthercatNetwork") -> None:
        """Test that context manager ensures network reference is set."""
        # Remove network from references (added when net is created)
        assert net_mocker in ETHERCAT_NETWORK_REFERENCES
        if net_mocker in ETHERCAT_NETWORK_REFERENCES:
            release_network_reference(network=net_mocker)
        assert net_mocker not in ETHERCAT_NETWORK_REFERENCES

        with net_mocker.running():
            assert net_mocker in ETHERCAT_NETWORK_REFERENCES

        assert net_mocker not in ETHERCAT_NETWORK_REFERENCES

    @pytest.mark.pcap
    def test_context_manager_handles_exceptions(self, net_mocker: "EthercatNetwork") -> None:
        """Test that context manager properly closes master even when exception occurs."""
        with pytest.raises(ValueError, match="test exception"), net_mocker.running():
            # Simulate master running
            net_mocker._EthercatNetwork__is_master_running = True
            raise ValueError("test exception")

        # Master should still be closed despite exception
        net_mocker.close_ecat_master.assert_called_once_with(release_reference=True)

    @pytest.mark.pcap
    def test_context_manager_reusable(self, net_mocker: "EthercatNetwork") -> None:
        """Test that context manager can be used multiple times on same network."""
        # Remove network from references (added when net is created)
        assert net_mocker in ETHERCAT_NETWORK_REFERENCES
        if net_mocker in ETHERCAT_NETWORK_REFERENCES:
            release_network_reference(network=net_mocker)
        assert net_mocker not in ETHERCAT_NETWORK_REFERENCES

        # First usage should add the reference and release it
        with net_mocker.running():
            assert net_mocker in ETHERCAT_NETWORK_REFERENCES
        assert net_mocker not in ETHERCAT_NETWORK_REFERENCES

        # Manually add the reference (simulate master already running)
        set_network_reference(network=net_mocker)
        net_mocker._EthercatNetwork__is_master_running = True

        # Second usage should not close the master since it was already running
        # and the reference should remain after context
        assert net_mocker in ETHERCAT_NETWORK_REFERENCES
        with net_mocker.running():
            assert net_mocker in ETHERCAT_NETWORK_REFERENCES
        assert net_mocker in ETHERCAT_NETWORK_REFERENCES

    @pytest.mark.ethercat
    def test_context_manager_nested_contexts(
        self, net: "EthercatNetwork", servo_with_reconnect: "ConnectionWrapper"
    ) -> None:
        """Test that nested context managers work correctly."""
        servo_with_reconnect.disconnect()

        # Network reference has been released with the disconnect, no master running
        assert net not in ETHERCAT_NETWORK_REFERENCES
        assert net._EthercatNetwork__is_master_running is False

        n_networks = len(ETHERCAT_NETWORK_REFERENCES)

        # Outer context starts the master
        with net.running():
            assert net._EthercatNetwork__is_master_running is True
            assert net in ETHERCAT_NETWORK_REFERENCES
            assert len(ETHERCAT_NETWORK_REFERENCES) == n_networks + 1

            with net.running():
                assert net._EthercatNetwork__is_master_running is True
                assert net in ETHERCAT_NETWORK_REFERENCES
                assert len(ETHERCAT_NETWORK_REFERENCES) == n_networks + 1

            # Master should still be running after nested scan_slaves()
            # (because outer context started it, not the internal scan_slaves() context)
            assert net._EthercatNetwork__is_master_running is True
            assert net in ETHERCAT_NETWORK_REFERENCES
            assert len(ETHERCAT_NETWORK_REFERENCES) == n_networks + 1

        # After outer context exits, master should be closed and reference released
        assert net._EthercatNetwork__is_master_running is False
        assert net not in ETHERCAT_NETWORK_REFERENCES
        assert len(ETHERCAT_NETWORK_REFERENCES) == n_networks
