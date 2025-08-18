import random
import time
from typing import TYPE_CHECKING, Optional

import pytest
from ingeniamotion.enums import OperationMode
from summit_testing_framework.setups.descriptors import EthercatMultiSlaveSetup

from ingenialink.exceptions import ILError, ILWrongWorkingCountError
from ingenialink.pdo import RPDOMap, RPDOMapItem, TPDOMap, TPDOMapItem
from ingenialink.pdo_network_manager import PDONetworkManager

if TYPE_CHECKING:
    from ingenialink.ethercat.network import EthercatNetwork
    from ingenialink.ethercat.servo import EthercatServo
    from ingenialink.pdo import PDOMap


DEFAULT_AXIS = 1


@pytest.mark.ethercat
def test_create_rpdo_item(servo: "EthercatServo") -> None:
    position_set_point_initial_value = 100
    position_set_point = PDONetworkManager.create_pdo_item(
        "CL_POS_SET_POINT_VALUE",
        servo=servo,
        value=position_set_point_initial_value,
        axis=DEFAULT_AXIS,
    )
    assert isinstance(position_set_point, RPDOMapItem)
    assert position_set_point.value == position_set_point_initial_value


@pytest.mark.ethercat
def test_create_tpdo_item(servo: "EthercatServo"):
    actual_position = PDONetworkManager.create_pdo_item(
        "CL_POS_FBK_VALUE", servo=servo, axis=DEFAULT_AXIS
    )
    assert isinstance(actual_position, TPDOMapItem)


@pytest.mark.ethercat
def test_create_rpdo_item_no_initial_value(servo: "EthercatServo"):
    with pytest.raises(AttributeError):
        PDONetworkManager.create_pdo_item("CL_POS_SET_POINT_VALUE", servo=servo, axis=DEFAULT_AXIS)


@pytest.mark.virtual
def test_create_empty_rpdo_map():
    rpdo_map = PDONetworkManager.create_empty_rpdo_map()
    assert isinstance(rpdo_map, RPDOMap)
    assert len(rpdo_map.items) == 0


@pytest.mark.virtual
def test_create_empty_tpdo_map():
    tpdo_map = PDONetworkManager.create_empty_tpdo_map()
    assert isinstance(tpdo_map, TPDOMap)
    assert len(tpdo_map.items) == 0


@pytest.mark.ethercat
def test_create_pdo_maps_single_item(servo: "EthercatServo"):
    position_set_point = PDONetworkManager.create_pdo_item(
        "CL_POS_SET_POINT_VALUE", servo=servo, value=0, axis=DEFAULT_AXIS
    )
    actual_position = PDONetworkManager.create_pdo_item(
        "CL_POS_FBK_VALUE", servo=servo, axis=DEFAULT_AXIS
    )
    rpdo_map, tpdo_map = PDONetworkManager.create_pdo_maps(position_set_point, actual_position)
    assert isinstance(rpdo_map, RPDOMap)
    assert len(rpdo_map.items) == 1
    assert position_set_point in rpdo_map.items
    assert isinstance(tpdo_map, TPDOMap)
    assert len(tpdo_map.items) == 1
    assert actual_position in tpdo_map.items


@pytest.mark.ethercat
def test_create_pdo_maps_list_items(servo: "EthercatServo"):
    rpdo_regs = ["CL_POS_SET_POINT_VALUE", "CL_VEL_SET_POINT_VALUE"]
    tpdo_regs = ["CL_POS_FBK_VALUE", "CL_VEL_FBK_VALUE"]
    rpdo_items = [
        PDONetworkManager.create_pdo_item(rpdo_reg, servo=servo, value=0, axis=DEFAULT_AXIS)
        for rpdo_reg in rpdo_regs
    ]
    tpdo_items = [
        PDONetworkManager.create_pdo_item(tpdo_reg, servo=servo, axis=DEFAULT_AXIS)
        for tpdo_reg in tpdo_regs
    ]
    rpdo_map, tpdo_map = PDONetworkManager.create_pdo_maps(rpdo_items, tpdo_items)
    assert isinstance(rpdo_map, RPDOMap)
    assert len(rpdo_map.items) == len(rpdo_items)
    assert isinstance(tpdo_map, TPDOMap)
    assert len(tpdo_map.items) == len(tpdo_items)


@pytest.mark.ethercat
@pytest.mark.parametrize(
    "register, value, pdo_type",
    [
        ("CL_POS_FBK_VALUE", None, "tpdo"),
        ("CL_VEL_SET_POINT_VALUE", 0, "rpdo"),
    ],
)
def test_add_pdo_item_to_map(
    servo: "EthercatServo", register: str, value: Optional[int], pdo_type: str
):
    if pdo_type == "rpdo":
        pdo_map = PDONetworkManager.create_empty_rpdo_map()
    else:
        pdo_map = PDONetworkManager.create_empty_tpdo_map()
    pdo_map_item = PDONetworkManager.create_pdo_item(
        register, servo=servo, value=value, axis=DEFAULT_AXIS
    )
    PDONetworkManager.add_pdo_item_to_map(pdo_map_item, pdo_map)
    assert len(pdo_map.items) == 1
    assert pdo_map_item in pdo_map.items


@pytest.mark.ethercat
@pytest.mark.parametrize(
    "register, value, pdo_type",
    [
        ("CL_POS_FBK_VALUE", None, "tpdo"),
        ("CL_VEL_SET_POINT_VALUE", 0, "rpdo"),
    ],
)
def test_add_pdo_item_to_map_exceptions(
    servo: "EthercatServo", register: str, value: Optional[int], pdo_type: str
) -> None:
    if pdo_type == "tpdo":
        pdo_map = PDONetworkManager.create_empty_rpdo_map()
    else:
        pdo_map = PDONetworkManager.create_empty_tpdo_map()
    pdo_map_item = PDONetworkManager.create_pdo_item(
        register, servo=servo, value=value, axis=DEFAULT_AXIS
    )
    with pytest.raises(ValueError):
        PDONetworkManager.add_pdo_item_to_map(pdo_map_item, pdo_map)


@pytest.mark.ethercat
@pytest.mark.parametrize(
    "rpdo_maps, tpdo_maps",
    [
        [["rpdo", "rpdo"], ["rpdo", "tpdo"]],
        [["rpdo", "tpdo"], ["tpdo", "tpdo"]],
    ],
)
def test_set_pdo_maps_to_slave_exception(
    servo: "EthercatServo", rpdo_maps: list[str], tpdo_maps: list[str]
) -> None:
    rx_maps = []
    tx_maps = []
    for map_type in rpdo_maps:
        pdo_map = (
            PDONetworkManager.create_empty_rpdo_map()
            if map_type == "rpdo"
            else PDONetworkManager.create_empty_tpdo_map()
        )
        rx_maps.append(pdo_map)
    for map_type in tpdo_maps:
        pdo_map = (
            PDONetworkManager.create_empty_rpdo_map()
            if map_type == "rpdo"
            else PDONetworkManager.create_empty_tpdo_map()
        )
        tx_maps.append(pdo_map)
    with pytest.raises(ValueError):
        PDONetworkManager.set_pdo_maps_to_slave(rx_maps, tx_maps, servo)


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
    rpdo_maps: dict[str, PDOMap] = {}
    tpdo_maps: dict[str, PDOMap] = {}
    for s, a in zip(servo, alias):
        rpdo_map = PDONetworkManager.create_empty_rpdo_map()
        tpdo_map = PDONetworkManager.create_empty_tpdo_map()
        initial_operation_mode = s.read("DRV_OP_CMD")
        operation_mode = PDONetworkManager.create_pdo_item(
            "DRV_OP_CMD", servo=s, value=initial_operation_mode.value, axis=DEFAULT_AXIS
        )
        actual_position = PDONetworkManager.create_pdo_item(
            "CL_POS_FBK_VALUE", servo=s, axis=DEFAULT_AXIS
        )
        PDONetworkManager.add_pdo_item_to_map(operation_mode, rpdo_map)
        PDONetworkManager.add_pdo_item_to_map(actual_position, tpdo_map)
        PDONetworkManager.set_pdo_maps_to_slave(rpdo_map, tpdo_map, servo=s)
        pdo_map_items[a] = (operation_mode, actual_position)
        random_op_mode = random.choice([
            op_mode for op_mode in OperationMode if op_mode != initial_operation_mode
        ])
        initial_operation_modes[a] = initial_operation_mode
        rpdo_values[a] = random_op_mode
        rpdo_maps[a] = rpdo_map
        tpdo_maps[a] = tpdo_map

    def send_callback():
        for a in alias:
            rpdo_map_item, _ = pdo_map_items[a]
            rpdo_map_item.value = rpdo_values[a].value

    def receive_callback():
        for a in alias:
            _, tpdo_map_item = pdo_map_items[a]
            tpdo_values[a] = tpdo_map_item.value

    for a in alias:
        rpdo_maps[a].subscribe_to_process_data_event(send_callback)
        tpdo_maps[a].subscribe_to_process_data_event(receive_callback)

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
        PDONetworkManager.remove_rpdo_map(servo=s, rpdo_map_index=0)
        PDONetworkManager.remove_tpdo_map(servo=s, tpdo_map_index=0)


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


@pytest.mark.ethercat
def test_subscribe_callbacks(net: "EthercatNetwork", servo: "EthercatServo", mocker) -> None:
    send_callback = mocker.Mock()
    receive_callback = mocker.Mock()

    rpdo_map = PDONetworkManager.create_empty_rpdo_map()
    tpdo_map = PDONetworkManager.create_empty_tpdo_map()
    initial_operation_mode = servo.read("DRV_OP_CMD")
    operation_mode = PDONetworkManager.create_pdo_item(
        "DRV_OP_CMD", servo=servo, value=initial_operation_mode, axis=DEFAULT_AXIS
    )
    actual_position = PDONetworkManager.create_pdo_item(
        "CL_POS_FBK_VALUE", servo=servo, axis=DEFAULT_AXIS
    )
    PDONetworkManager.add_pdo_item_to_map(operation_mode, rpdo_map)
    PDONetworkManager.add_pdo_item_to_map(actual_position, tpdo_map)
    PDONetworkManager.set_pdo_maps_to_slave(rpdo_maps=rpdo_map, tpdo_maps=tpdo_map, servo=servo)

    rpdo_map.subscribe_to_process_data_event(send_callback)
    tpdo_map.subscribe_to_process_data_event(receive_callback)

    assert send_callback.call_count == 0
    assert receive_callback.call_count == 0

    assert not net.pdo_manager.is_active
    refresh_rate = 0.5
    net.activate_pdos(refresh_rate=refresh_rate)
    assert net.pdo_manager.is_active
    time.sleep(2 * refresh_rate)
    net.deactivate_pdos()

    assert send_callback.call_count > 0
    assert receive_callback.call_count > 0
