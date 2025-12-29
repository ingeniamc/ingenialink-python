from typing import TYPE_CHECKING, Union

import pytest

from ingenialink.drive_context_manager import DriveContextManager
from ingenialink.pdo import RPDOMap, TPDOMap

if TYPE_CHECKING:
    from summit_testing_framework.setups.descriptors import DriveEcatSetup
    from summit_testing_framework.setups.environment_control import DriveEnvironmentController

    from ingenialink.ethercat.network import EthercatNetwork
    from ingenialink.network import Network

_USER_OVER_VOLTAGE_UID = "DRV_PROT_USER_OVER_VOLT"
_USER_UNDER_VOLTAGE_UID = "DRV_PROT_USER_UNDER_VOLT"


def _read_user_over_voltage_uid(servo):
    return servo.read(_USER_OVER_VOLTAGE_UID, subnode=1)


def _read_user_under_voltage_uid(servo):
    return servo.read(_USER_UNDER_VOLTAGE_UID, subnode=1)


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_drive_context_manager(
    setup_manager: tuple["Network", Union[str, list[str]], "DriveEnvironmentController"],
):
    net, _, _ = setup_manager
    servo = net.servos[0]
    context = DriveContextManager(servo)

    new_reg_value = 100.0
    previous_reg_value = _read_user_over_voltage_uid(servo)
    if previous_reg_value == new_reg_value:
        new_reg_value -= 1.0
    new_reg_value_2 = new_reg_value - 10
    if previous_reg_value == new_reg_value_2:
        new_reg_value_2 -= 1.0

    with context:
        servo.write(_USER_OVER_VOLTAGE_UID, new_reg_value, subnode=1)
        assert _read_user_over_voltage_uid(servo) == new_reg_value
        assert context._registers_changed == {(1, _USER_OVER_VOLTAGE_UID): new_reg_value}

        # Change the register a second time, it should register the change
        servo.write(_USER_OVER_VOLTAGE_UID, new_reg_value_2, subnode=1)
        assert _read_user_over_voltage_uid(servo) == new_reg_value_2
        assert context._registers_changed == {(1, _USER_OVER_VOLTAGE_UID): new_reg_value_2}

    assert _read_user_over_voltage_uid(servo) == previous_reg_value


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_drive_context_manager_nested_contexts(
    setup_manager: tuple["Network", Union[str, list[str]], "DriveEnvironmentController"],
):
    net, _, _ = setup_manager
    servo = net.servos[0]
    context = DriveContextManager(servo)

    new_over_volt_value = 100.0
    previous_over_volt_value = _read_user_over_voltage_uid(servo)
    if previous_over_volt_value == new_over_volt_value:
        new_over_volt_value -= 1.0

    new_under_volt_value = 1.0
    previous_under_volt_value = _read_user_under_voltage_uid(servo)
    assert previous_under_volt_value != new_under_volt_value
    if previous_under_volt_value == new_under_volt_value:
        new_under_volt_value += 1.0

    with context:
        servo.write(_USER_OVER_VOLTAGE_UID, new_over_volt_value, subnode=1)
        assert _read_user_over_voltage_uid(servo) == new_over_volt_value

        context_2 = DriveContextManager(servo)
        with context_2:
            servo.write(_USER_UNDER_VOLTAGE_UID, new_under_volt_value, subnode=1)
            assert _read_user_under_voltage_uid(servo) == new_under_volt_value

        assert _read_user_under_voltage_uid(servo) == previous_under_volt_value

    assert _read_user_over_voltage_uid(servo) == previous_over_volt_value


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_drive_context_manager_skips_default_do_not_restore_registers(
    setup_manager: tuple["Network", Union[str, list[str]], "DriveEnvironmentController"],
):
    net, _, _ = setup_manager
    servo = net.servos[0]
    context = DriveContextManager(servo)
    assert len(context._do_not_restore_registers) == 5

    # If not additional ignored registers are added,
    # the default ones are the ones that are troublesome
    # because they have a specific password, that is written but not read.
    assert context._do_not_restore_registers == {
        servo.STORE_COCO_ALL,
        servo.STORE_MOCO_ALL_REGISTERS,
        servo.RESTORE_COCO_ALL,
        servo.RESTORE_MOCO_ALL_REGISTERS,
        "COMMS_ETH_MAC",
    }


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_drive_context_manager_with_do_not_restore_registers(
    setup_manager: tuple["Network", Union[str, list[str]], "DriveEnvironmentController"],
):
    net, _, _ = setup_manager
    servo = net.servos[0]
    context = DriveContextManager(servo, do_not_restore_registers=[_USER_OVER_VOLTAGE_UID])
    assert (
        len(context._do_not_restore_registers) == 6
    )  # COCO-MOCO store/restore registers + _USER_OVER_VOLTAGE_UID

    new_reg_value = 100.0
    previous_reg_value = _read_user_over_voltage_uid(servo)
    if previous_reg_value == new_reg_value:
        new_reg_value -= 1.0

    with context:
        servo.write(_USER_OVER_VOLTAGE_UID, new_reg_value, subnode=1)
        assert _read_user_over_voltage_uid(servo) == new_reg_value

    assert _read_user_over_voltage_uid(servo) == new_reg_value


@pytest.mark.ethercat
def test_drive_context_manager_restores_complete_access_registers(
    setup_manager: tuple["EthercatNetwork", str, "DriveEnvironmentController"],
    setup_descriptor: "DriveEcatSetup",
) -> None:
    net, _, _ = setup_manager
    servo = net.servos[0]
    context = DriveContextManager(servo)

    servo.reset_rpdo_mapping()
    servo.reset_tpdo_mapping()

    tpdo_map = TPDOMap()
    tpdo_registers = ["CL_POS_FBK_VALUE", "CL_VEL_FBK_VALUE", "CL_TOR_FBK_VALUE"]
    for tpdo_register in tpdo_registers:
        register = servo.dictionary.get_register(tpdo_register)
        tpdo_map.add_registers(register)

    rpdo_map = RPDOMap()
    rpdo_registers = ["CL_POS_SET_POINT_VALUE", "CL_VEL_SET_POINT_VALUE", "CL_TOR_SET_POINT_VALUE"]
    for rpdo_register in rpdo_registers:
        register = servo.dictionary.get_register(rpdo_register)
        rpdo_map.add_registers(register)

    with context:
        assert context._registers_changed == {}
        assert context._objects_changed == set()
        servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
        servo.map_pdos(slave_index=setup_descriptor.slave)

        assert (0, "ETG_COMMS_RPDO_ASSIGN_TOTAL") in context._registers_changed
        assert (0, "ETG_COMMS_TPDO_ASSIGN_TOTAL") in context._registers_changed
        assert len(context._objects_changed) == 4
        objects_uids = [obj.uid for obj in context._objects_changed]
        assert "ETG_COMMS_RPDO_ASSIGN" in objects_uids
        assert "ETG_COMMS_TPDO_ASSIGN" in objects_uids
        assert "ETG_COMMS_RPDO_MAP1" in objects_uids
        assert "ETG_COMMS_TPDO_MAP1" in objects_uids


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_force_restore_with_external_changes(
    setup_manager: tuple["Network", Union[str, list[str]], "DriveEnvironmentController"],
) -> None:
    """Test that force_restore detects and restores changes made outside the context manager."""
    net, _, _ = setup_manager
    servo = net.servos[0]
    context = DriveContextManager(servo)

    new_over_volt_value = 100.0
    previous_over_volt_value = _read_user_over_voltage_uid(servo)
    if previous_over_volt_value == new_over_volt_value:
        new_over_volt_value -= 1.0

    new_under_volt_value = 1.0
    previous_under_volt_value = _read_user_under_voltage_uid(servo)
    if previous_under_volt_value == new_under_volt_value:
        new_under_volt_value += 1.0

    with context:
        # Make a tracked change
        servo.write(_USER_OVER_VOLTAGE_UID, new_over_volt_value, subnode=1)
        assert _read_user_over_voltage_uid(servo) == new_over_volt_value
        assert (1, _USER_OVER_VOLTAGE_UID) in context._registers_changed

        # Simulate an external change (bypass the callback by directly modifying the drive)
        # In reality, this would be done by another process/connection
        servo.write(_USER_UNDER_VOLTAGE_UID, new_under_volt_value, subnode=1)

        # Clear the tracking to simulate that this change wasn't tracked
        context._registers_changed.pop((1, _USER_UNDER_VOLTAGE_UID), None)

        # Verify the external change is present
        assert _read_user_under_voltage_uid(servo) == new_under_volt_value

        # Force restore should detect and restore both changes
        context.force_restore()

        # Both registers should now be back to original values
        assert _read_user_over_voltage_uid(servo) == previous_over_volt_value
        assert _read_user_under_voltage_uid(servo) == previous_under_volt_value

        # Tracking should be cleared
        assert context._registers_changed == {}
        assert context._objects_changed == {}


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_force_restore_clears_tracking(
    setup_manager: tuple["Network", Union[str, list[str]], "DriveEnvironmentController"],
) -> None:
    """Test that force_restore clears the internal tracking dictionaries."""
    net, _, _ = setup_manager
    servo = net.servos[0]
    context = DriveContextManager(servo)

    new_reg_value = 100.0
    previous_reg_value = _read_user_over_voltage_uid(servo)
    if previous_reg_value == new_reg_value:
        new_reg_value -= 1.0

    with context:
        # Make changes
        servo.write(_USER_OVER_VOLTAGE_UID, new_reg_value, subnode=1)
        assert (1, _USER_OVER_VOLTAGE_UID) in context._registers_changed

        # Force restore
        context.force_restore()

        # Verify tracking is cleared
        assert context._registers_changed == {}
        assert context._objects_changed == {}

        # Verify register was restored
        assert _read_user_over_voltage_uid(servo) == previous_reg_value


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_force_restore_only_restores_changed_values(
    setup_manager: tuple["Network", Union[str, list[str]], "DriveEnvironmentController"],
) -> None:
    """Test that force_restore only restores registers that have actually changed."""
    net, _, _ = setup_manager
    servo = net.servos[0]
    context = DriveContextManager(servo)

    new_reg_value = 100.0
    previous_over_volt_value = _read_user_over_voltage_uid(servo)
    if previous_over_volt_value == new_reg_value:
        new_reg_value -= 1.0

    previous_under_volt_value = _read_user_under_voltage_uid(servo)

    with context:
        # Change only one register
        servo.write(_USER_OVER_VOLTAGE_UID, new_reg_value, subnode=1)
        assert _read_user_over_voltage_uid(servo) == new_reg_value

        # The other register should still have its original value
        assert _read_user_under_voltage_uid(servo) == previous_under_volt_value

        # Force restore should only restore the changed register
        context.force_restore()

        # Changed register should be restored
        assert _read_user_over_voltage_uid(servo) == previous_over_volt_value
        # Unchanged register should still have original value
        assert _read_user_under_voltage_uid(servo) == previous_under_volt_value


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_force_restore_multiple_times(
    setup_manager: tuple["Network", Union[str, list[str]], "DriveEnvironmentController"],
) -> None:
    """Test that force_restore can be called multiple times."""
    net, _, _ = setup_manager
    servo = net.servos[0]
    context = DriveContextManager(servo)

    new_reg_value = 100.0
    previous_reg_value = _read_user_over_voltage_uid(servo)
    if previous_reg_value == new_reg_value:
        new_reg_value -= 1.0

    with context:
        # Make a change
        servo.write(_USER_OVER_VOLTAGE_UID, new_reg_value, subnode=1)
        assert _read_user_over_voltage_uid(servo) == new_reg_value

        # First force restore
        context.force_restore()
        assert _read_user_over_voltage_uid(servo) == previous_reg_value

        # Make another change
        new_reg_value_2 = new_reg_value - 10
        if previous_reg_value == new_reg_value_2:
            new_reg_value_2 -= 1.0
        servo.write(_USER_OVER_VOLTAGE_UID, new_reg_value_2, subnode=1)
        assert _read_user_over_voltage_uid(servo) == new_reg_value_2

        # Second force restore
        context.force_restore()
        assert _read_user_over_voltage_uid(servo) == previous_reg_value


@pytest.mark.ethercat
def test_force_restore_with_complete_access_objects(
    setup_manager: tuple["EthercatNetwork", str, "DriveEnvironmentController"],
    setup_descriptor: "DriveEcatSetup",
) -> None:
    """Test that force_restore works with complete access objects (PDO mappings)."""
    net, _, _ = setup_manager
    servo = net.servos[0]
    context = DriveContextManager(servo)

    # Store original PDO state
    servo.reset_rpdo_mapping()
    servo.reset_tpdo_mapping()

    tpdo_map = TPDOMap()
    tpdo_registers = ["CL_POS_FBK_VALUE", "CL_VEL_FBK_VALUE"]
    for tpdo_register in tpdo_registers:
        register = servo.dictionary.get_register(tpdo_register)
        tpdo_map.add_registers(register)

    rpdo_map = RPDOMap()
    rpdo_registers = ["CL_POS_SET_POINT_VALUE", "CL_VEL_SET_POINT_VALUE"]
    for rpdo_register in rpdo_registers:
        register = servo.dictionary.get_register(rpdo_register)
        rpdo_map.add_registers(register)

    with context:
        # Change PDO mappings
        servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
        servo.map_pdos(slave_index=setup_descriptor.slave)

        assert len(context._objects_changed) > 0

        # Force restore should restore PDO mappings to original state
        context.force_restore()

        # Tracking should be cleared
        assert context._objects_changed == {}
