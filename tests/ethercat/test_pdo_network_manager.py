import random
import time
from typing import TYPE_CHECKING

import pytest
from summit_testing_framework.setups.descriptors import EthercatMultiSlaveSetup

from ingenialink.exceptions import ILError, ILWrongWorkingCountError
from ingenialink.pdo import PDOMap, RPDOMap, TPDOMap
from ingenialink.pdo_network_manager import PDONetworkManager

if TYPE_CHECKING:
    from ingenialink.ethercat.network import EthercatNetwork
    from ingenialink.ethercat.servo import EthercatServo


@pytest.mark.ethercat
def test_pdos_min_refresh_rate(net: "EthercatNetwork"):
    refresh_rate = 0.0001
    with pytest.raises(ValueError):
        net.activate_pdos(refresh_rate=refresh_rate)


@pytest.mark.ethercat
def test_pdos_watchdog_exception_auto(net: "EthercatNetwork"):
    exceptions = []

    def exception_callback(exc):
        exceptions.append(exc)

    refresh_rate = 3.5
    net.pdo_manager.subscribe_to_exceptions(exception_callback)
    net.activate_pdos(refresh_rate=refresh_rate)
    time.sleep(1)
    net.pdo_manager.unsubscribe_to_exceptions(exception_callback)
    assert len(exceptions) > 0
    exception = exceptions[0]
    assert str(exception) == "The sampling time is too high. The max sampling time is 3276.75 ms."


@pytest.mark.ethercat
def test_pdos_watchdog_exception_manual(net: "EthercatNetwork"):
    exceptions = []

    def exception_callback(exc):
        exceptions.append(exc)

    watchdog_timeout = 7
    net.pdo_manager.subscribe_to_exceptions(exception_callback)
    net.activate_pdos(watchdog_timeout=watchdog_timeout)
    time.sleep(1)
    net.pdo_manager.unsubscribe_to_exceptions(exception_callback)
    assert len(exceptions) > 0
    exception = exceptions[0]
    assert (
        str(exception) == "The watchdog timeout is too high. The max watchdog timeout is 6553.5 ms."
    )


@pytest.mark.multislave
def test_start_pdos(
    net: "EthercatNetwork",
    servo: list["EthercatServo"],
    alias: list[str],
    setup_descriptor,
):
    if not isinstance(setup_descriptor, EthercatMultiSlaveSetup):
        raise ValueError("Invalid setup config for test")

    pdo_map_items = {}
    initial_operation_modes = {}
    rpdo_values = {}
    tpdo_values = {}
    for s, a in zip(servo, alias):
        rpdo_map = RPDOMap()
        tpdo_map = TPDOMap()
        initial_operation_mode = s.read("DRV_OP_CMD")
        operation_mode = PDOMap.create_item_from_register_uid(
            "DRV_OP_CMD", dictionary=s.dictionary, value=initial_operation_mode, axis=1
        )
        actual_position = PDOMap.create_item_from_register_uid(
            "CL_POS_FBK_VALUE", dictionary=s.dictionary, axis=1
        )
        rpdo_map.add_item(operation_mode)
        tpdo_map.add_item(actual_position)
        s.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
        pdo_map_items[a] = (operation_mode, actual_position)
        # Choose a random operation mode: [voltage, current, velocity, position]
        random_op_mode = random.choice([
            op_mode for op_mode in [0x00, 0x02, 0x03, 0x04] if op_mode != initial_operation_mode
        ])
        initial_operation_modes[a] = initial_operation_mode
        rpdo_values[a] = random_op_mode

    def send_callback():
        for a in alias:
            rpdo_map_item, _ = pdo_map_items[a]
            rpdo_map_item.value = rpdo_values[a]

    def receive_callback():
        for a in alias:
            _, tpdo_map_item = pdo_map_items[a]
            tpdo_values[a] = tpdo_map_item.value

    net.pdo_manager.subscribe_to_send_process_data(send_callback)
    net.pdo_manager.subscribe_to_receive_process_data(receive_callback)
    assert not net.pdo_manager.is_active
    refresh_rate = 0.5
    net.activate_pdos(refresh_rate=refresh_rate)
    assert net.pdo_manager.is_active
    time.sleep(2 * refresh_rate)
    net.deactivate_pdos()
    assert not net.pdo_manager.is_active
    for s, a in zip(servo, alias):
        # Check that RPDO are being sent
        assert rpdo_values[a] == s.read("DRV_OP_CMD")
        # Check that TPDO are being received
        assert pytest.approx(tpdo_values[a], abs=2) == s.read("CL_POS_FBK_VALUE")
        # Restore the initial operation mode
        s.write("DRV_OP_CMD", initial_operation_modes[a])
        s.remove_rpdo_map(rpdo_map_index=0)
        s.remove_tpdo_map(tpdo_map_index=0)


@pytest.mark.ethercat
def test_stop_pdos_exception(net: "EthercatNetwork") -> None:
    with pytest.raises(ILError):
        net.deactivate_pdos()


@pytest.mark.ethercat
def test_subscribe_exceptions(net: "EthercatNetwork", mocker) -> None:
    error_msg = "Test error"

    def start_pdos(*_):
        raise ILWrongWorkingCountError(error_msg)

    mocker.patch("ingenialink.ethercat.network.EthercatNetwork.stop_pdos")
    mocker.patch(
        "ingenialink.ethercat.network.EthercatNetwork.start_pdos",
        new=start_pdos,
    )
    patch_callback = mocker.patch(
        "ingenialink.pdo_network_manager.PDONetworkManager._notify_exceptions"
    )

    net.pdo_manager.subscribe_to_exceptions(patch_callback)
    net.activate_pdos()

    t = time.time()
    timeout = 1
    while not net.pdo_manager._pdo_thread._pd_thread_stop_event.is_set() and (
        (time.time() - t) < timeout
    ):
        pass

    assert net.pdo_manager._pdo_thread._pd_thread_stop_event.is_set()
    patch_callback.assert_called_once()
    assert (
        str(patch_callback.call_args_list[0][0][0])
        == f"Stopping the PDO thread due to the following exception: {error_msg} "
    )
    net.deactivate_pdos()


@pytest.mark.ethercat
def test_subscribe_to_pdo_thread_status(net: "EthercatNetwork", mocker) -> None:
    status = None

    def status_callback(new_status):
        nonlocal status
        status = new_status

    mocker.patch.object(PDONetworkManager, "start_pdos")
    mocker.patch.object(PDONetworkManager, "stop_pdos")

    net.subscribe_to_pdo_thread_status(status_callback)

    assert status is None
    net.activate_pdos()
    assert status is True
    net.deactivate_pdos()
    assert status is False
