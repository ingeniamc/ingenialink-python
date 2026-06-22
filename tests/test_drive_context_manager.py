from collections import OrderedDict

import pytest
from pytest_mock import MockerFixture

from ingenialink.drive_context_manager import (
    DriveContextManager,
    DriveRegistersSession,
    DriveRegistersValue,
    FailedEntry,
    RestoredEntry,
    RestoreResult,
    SkippedEntry,
    _write_with_retry,
)
from ingenialink.enums.register import RegAccess, RegDtype
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.ethercat.state import SlaveState
from ingenialink.pdo import RPDOMap, TPDOMap
from ingenialink.register import Register
from ingenialink.servo import Servo

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
def test_drive_context_manager(servo: "Servo"):
    context = DriveContextManager(servo)

    new_reg_value = 100.0
    previous_reg_value = _read_user_over_voltage_uid(servo)
    if previous_reg_value == new_reg_value:
        new_reg_value -= 1.0
    new_reg_value_2 = new_reg_value - 10
    if previous_reg_value == new_reg_value_2:
        new_reg_value_2 -= 1.0

    over_volt_reg = servo.dictionary.get_register(_USER_OVER_VOLTAGE_UID, axis=1)

    with context:
        servo.write(_USER_OVER_VOLTAGE_UID, new_reg_value, subnode=1)
        assert _read_user_over_voltage_uid(servo) == new_reg_value
        assert context._session._changes[over_volt_reg] == new_reg_value

        # Change the register a second time, it should register the change
        servo.write(_USER_OVER_VOLTAGE_UID, new_reg_value_2, subnode=1)
        assert _read_user_over_voltage_uid(servo) == new_reg_value_2
        assert context._session._changes[over_volt_reg] == new_reg_value_2

    assert _read_user_over_voltage_uid(servo) == previous_reg_value


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_drive_context_manager_nested_contexts(servo: "Servo"):
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
def test_drive_context_manager_skips_default_do_not_restore_registers(servo: "Servo"):
    context = DriveContextManager(servo)

    expected = set(
        servo.dictionary.find_registers(
            servo.STORE_COCO_ALL,
            servo.STORE_MOCO_ALL_REGISTERS,
            servo.RESTORE_COCO_ALL,
            servo.RESTORE_MOCO_ALL_REGISTERS,
            "COMMS_ETH_MAC",
            "ETG_ERROR_FIELD",
            "CIA301_COMMS_ERROR_FIELD",
            # EtherCAT dictionaries also exclude PDO MAP registers (restored via
            # complete access).  ASSIGN registers are NOT excluded.
            "ETG_COMMS_RPDO_MAP*",
            "ETG_COMMS_TPDO_MAP*",
        )
    )

    assert context._do_not_restore_registers == expected


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_drive_context_manager_with_do_not_restore_registers(servo: "Servo"):
    context = DriveContextManager(servo, do_not_restore_registers=[_USER_OVER_VOLTAGE_UID])

    expected = set(
        servo.dictionary.find_registers(
            servo.STORE_COCO_ALL,
            servo.STORE_MOCO_ALL_REGISTERS,
            servo.RESTORE_COCO_ALL,
            servo.RESTORE_MOCO_ALL_REGISTERS,
            "COMMS_ETH_MAC",
            "ETG_ERROR_FIELD",
            "CIA301_COMMS_ERROR_FIELD",
            _USER_OVER_VOLTAGE_UID,
            "ETG_COMMS_RPDO_MAP*",
            "ETG_COMMS_TPDO_MAP*",
        )
    )

    assert context._do_not_restore_registers == expected

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
    servo: "Servo", setup_descriptor
) -> None:
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

    rpdo_assign_total_reg = servo.dictionary.get_register("ETG_COMMS_RPDO_ASSIGN_TOTAL", axis=0)
    tpdo_assign_total_reg = servo.dictionary.get_register("ETG_COMMS_TPDO_ASSIGN_TOTAL", axis=0)

    with context:
        assert context._session.changes == {}
        assert context._objects_changed == {}
        servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])
        servo.map_pdos(slave_index=setup_descriptor.slave)

        assert rpdo_assign_total_reg in context._session.changes
        assert tpdo_assign_total_reg in context._session.changes
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
def test_force_restore_with_external_changes(servo: "Servo") -> None:
    """Test that force_restore detects and restores changes made outside the context manager."""
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
        over_volt_reg = servo.dictionary.get_register(_USER_OVER_VOLTAGE_UID, axis=1)
        assert over_volt_reg in context._session.changes

        # Simulate an external change (bypass the callback by directly modifying the drive)
        # In reality, this would be done by another process/connection
        servo.write(_USER_UNDER_VOLTAGE_UID, new_under_volt_value, subnode=1)

        # Clear the tracking to simulate that this change wasn't tracked
        under_volt_reg = servo.dictionary.get_register(_USER_UNDER_VOLTAGE_UID, axis=1)
        context._session._changes.pop(under_volt_reg, None)

        # Verify the external change is present
        assert _read_user_under_voltage_uid(servo) == new_under_volt_value

        # Force restore should detect and restore both changes
        context.force_restore()

        # Both registers should now be back to original values
        assert _read_user_over_voltage_uid(servo) == previous_over_volt_value
        assert _read_user_under_voltage_uid(servo) == previous_under_volt_value

        # Tracking should be cleared
        assert context._session.changes == {}
        assert context._objects_changed == {}


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_force_restore_clears_tracking(servo: "Servo") -> None:
    """Test that force_restore clears the internal tracking dictionaries."""
    context = DriveContextManager(servo)

    new_reg_value = 100.0
    previous_reg_value = _read_user_over_voltage_uid(servo)
    if previous_reg_value == new_reg_value:
        new_reg_value -= 1.0

    over_volt_reg = servo.dictionary.get_register(_USER_OVER_VOLTAGE_UID, axis=1)

    with context:
        # Make changes
        servo.write(_USER_OVER_VOLTAGE_UID, new_reg_value, subnode=1)
        assert over_volt_reg in context._session.changes

        # Force restore
        context.force_restore()

        # Verify tracking is cleared
        assert context._session.changes == {}
        assert context._objects_changed == {}

        # Verify register was restored
        assert _read_user_over_voltage_uid(servo) == previous_reg_value


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_force_restore_only_restores_changed_values(servo: "Servo") -> None:
    """Test that force_restore only restores registers that have actually changed."""
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
def test_force_restore_multiple_times(servo: "Servo") -> None:
    """Test that force_restore can be called multiple times."""
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
def test_force_restore_with_complete_access_objects(servo: "Servo", setup_descriptor) -> None:
    """Test that force_restore works with complete access objects (PDO mappings)."""
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


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_drive_context_manager_with_baseline(servo: "Servo") -> None:
    """Test that passing a pre-built baseline skips the from_hardware() read in __enter__."""

    # Build a baseline snapshot from hardware
    baseline = DriveRegistersValue.from_hardware(servo)

    # Create context manager with the pre-built baseline
    context = DriveContextManager(servo, baseline=baseline)

    new_reg_value = 100.0
    previous_reg_value = _read_user_over_voltage_uid(servo)
    if previous_reg_value == new_reg_value:
        new_reg_value -= 1.0

    with context:
        # The context should use the pre-built baseline (not read from hardware again)
        assert context._baseline is baseline

        # Verify tracking and restoration still work
        servo.write(_USER_OVER_VOLTAGE_UID, new_reg_value, subnode=1)
        assert _read_user_over_voltage_uid(servo) == new_reg_value
        over_volt_reg = servo.dictionary.get_register(_USER_OVER_VOLTAGE_UID, axis=1)
        assert over_volt_reg in context._session.changes

    # Registers should be restored
    assert _read_user_over_voltage_uid(servo) == previous_reg_value


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_drive_registers_state_diff(servo: "Servo") -> None:
    """diff() returns registers whose values differ between two snapshots."""

    state_before = DriveRegistersValue.from_hardware(servo)

    new_reg_value = 100.0
    previous_reg_value = _read_user_over_voltage_uid(servo)
    if previous_reg_value == new_reg_value:
        new_reg_value -= 1.0

    servo.write(_USER_OVER_VOLTAGE_UID, new_reg_value, subnode=1)
    try:
        state_after = DriveRegistersValue.from_hardware(servo)

        differences = state_before.diff(state_after)
        diff_uids = {reg.identifier for reg in differences}
        assert _USER_OVER_VOLTAGE_UID in diff_uids

        # The tuple should be (before_value, after_value)
        for reg, (before_val, after_val) in differences.items():
            if reg.identifier == _USER_OVER_VOLTAGE_UID:
                assert before_val == previous_reg_value
                assert after_val == new_reg_value
    finally:
        servo.write(_USER_OVER_VOLTAGE_UID, previous_reg_value, subnode=1)


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_drive_registers_state_from_dict(servo: "Servo") -> None:
    """from_dict() builds a state from an existing register-to-value mapping."""

    register = servo.dictionary.get_register(_USER_OVER_VOLTAGE_UID, axis=1)
    data: OrderedDict = OrderedDict([(register, 42.0)])
    state = DriveRegistersValue.from_dict(data)

    assert state.get(register) == 42.0


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_drive_registers_state_get(servo: "Servo") -> None:
    """get() returns a register value or None if not present."""

    state = DriveRegistersValue.from_hardware(servo)

    register = servo.dictionary.get_register(_USER_OVER_VOLTAGE_UID, axis=1)
    value = state.get(register)
    assert value is not None
    assert value == _read_user_over_voltage_uid(servo)

    # A RO register is excluded by from_hardware, so get() should return None
    missing_register = servo.dictionary.get_register("DRV_STATE_STATUS", axis=1)
    assert state.get(missing_register) is None


class TestRestoreResult:
    """Tests for the RestoreResult structured result class."""

    def test_empty(self):
        """An empty RestoreResult reports success with a clean summary."""
        result = RestoreResult()
        assert result.all_succeeded is True
        assert result.summary() == "Restored: 0"

    def test_with_failures(self):
        """A RestoreResult with failures reports not-all-succeeded."""
        result = RestoreResult()
        reg = Register(dtype=RegDtype.FLOAT, access=RegAccess.RW, identifier="TEST_REG")
        result.restored.append(RestoredEntry(reg, 1.0))
        result.failed.append(FailedEntry(reg, 2.0, RuntimeError("boom")))
        result.skipped.append(SkippedEntry(reg, "reason"))

        assert result.all_succeeded is False
        assert result.summary() == "Restored: 1, Failed: 1, Skipped: 1"

    def test_summary_only_restored(self):
        """summary() omits Failed and Skipped sections when only restores exist."""
        result = RestoreResult()
        reg = Register(dtype=RegDtype.FLOAT, access=RegAccess.RW, identifier="REG1")
        result.restored.append(RestoredEntry(reg, 1.0))
        assert result.summary() == "Restored: 1"

    def test_summary_with_failed_only(self):
        """summary() omits Skipped section when only failures exist."""
        result = RestoreResult()
        reg = Register(dtype=RegDtype.FLOAT, access=RegAccess.RW, identifier="REG1")
        result.failed.append(FailedEntry(reg, 1.0, RuntimeError("boom")))
        assert result.summary() == "Restored: 0, Failed: 1"


class TestDriveRegistersSession:
    """Tests for DriveRegistersSession methods."""

    @pytest.mark.ethernet
    @pytest.mark.ethercat
    @pytest.mark.canopen
    @pytest.mark.virtual
    def test_state_merges_baseline_and_changes(
        self,
        servo: "Servo",
    ) -> None:
        """state() returns baseline values overlaid with tracked changes."""

        baseline = DriveRegistersValue.from_hardware(servo)
        session = DriveRegistersSession(
            servo=servo,
            baseline=baseline,
            do_not_restore_registers=set(),
        )

        register = servo.dictionary.get_register(_USER_OVER_VOLTAGE_UID, axis=1)
        original_value = baseline.get(register)

        # Before any changes, current_value() should equal baseline
        state = session.current_value()
        assert state.get(register) == original_value

        # Simulate a tracked change
        new_value = 123.0
        session._changes[register] = new_value

        state = session.current_value()
        assert state.get(register) == new_value

    @pytest.mark.ethernet
    @pytest.mark.ethercat
    @pytest.mark.canopen
    @pytest.mark.virtual
    def test_restore_returns_result(
        self,
        servo: "Servo",
    ) -> None:
        """restore() writes baseline values back and returns a RestoreResult."""

        previous_reg_value = _read_user_over_voltage_uid(servo)
        baseline = DriveRegistersValue.from_hardware(servo)
        session = DriveRegistersSession(
            servo=servo,
            baseline=baseline,
            do_not_restore_registers=set(),
        )
        session.start()

        new_reg_value = 100.0
        if previous_reg_value == new_reg_value:
            new_reg_value -= 1.0

        servo.write(_USER_OVER_VOLTAGE_UID, new_reg_value, subnode=1)
        assert _read_user_over_voltage_uid(servo) == new_reg_value

        session.stop()
        result = session.restore()

        assert isinstance(result, RestoreResult)
        assert result.all_succeeded
        assert len(result.restored) >= 1
        assert _read_user_over_voltage_uid(servo) == previous_reg_value

    @pytest.mark.ethernet
    @pytest.mark.ethercat
    @pytest.mark.canopen
    @pytest.mark.virtual
    def test_force_restore_returns_result(
        self,
        servo: "Servo",
    ) -> None:
        """force_restore() re-reads hardware, diffs, restores, and returns a RestoreResult."""

        previous_reg_value = _read_user_over_voltage_uid(servo)
        baseline = DriveRegistersValue.from_hardware(servo)
        session = DriveRegistersSession(
            servo=servo,
            baseline=baseline,
            do_not_restore_registers=set(),
        )

        new_reg_value = 100.0
        if previous_reg_value == new_reg_value:
            new_reg_value -= 1.0

        # Write directly. session is NOT subscribed, simulating external change
        servo.write(_USER_OVER_VOLTAGE_UID, new_reg_value, subnode=1)
        assert _read_user_over_voltage_uid(servo) == new_reg_value

        result = session.force_restore()

        assert isinstance(result, RestoreResult)
        assert result.all_succeeded
        assert len(result.restored) >= 1
        assert _read_user_over_voltage_uid(servo) == previous_reg_value
        # force_restore clears changes
        assert len(session._changes) == 0

    def test_write_with_retry_succeeds_first_attempt(self, mocker: MockerFixture):
        """_write_with_retry records success on first write attempt."""
        servo_mock = mocker.MagicMock(spec=Servo)
        reg = Register(dtype=RegDtype.FLOAT, access=RegAccess.RW, identifier="TEST_REG")

        result = RestoreResult()
        _write_with_retry(servo_mock, reg, 42.0, result, max_attempts=2)

        servo_mock.write.assert_called_once_with(reg, 42.0)
        assert len(result.restored) == 1
        assert len(result.failed) == 0

    def test_write_with_retry_retries_on_failure(self, mocker: MockerFixture):
        """_write_with_retry retries and succeeds on second attempt."""
        servo_mock = mocker.MagicMock(spec=Servo)
        servo_mock.write.side_effect = [RuntimeError("first fail"), None]
        reg = Register(dtype=RegDtype.FLOAT, access=RegAccess.RW, identifier="TEST_REG")

        result = RestoreResult()
        _write_with_retry(servo_mock, reg, 42.0, result, max_attempts=2)

        assert servo_mock.write.call_count == 2
        assert len(result.restored) == 1
        assert len(result.failed) == 0

    def test_write_with_retry_fails_after_max_attempts(self, mocker: MockerFixture):
        """_write_with_retry records failure when all attempts fail."""
        servo_mock = mocker.MagicMock(spec=Servo)
        servo_mock.write.side_effect = RuntimeError("persistent error")
        reg = Register(dtype=RegDtype.FLOAT, access=RegAccess.RW, identifier="TEST_REG")

        result = RestoreResult()
        _write_with_retry(servo_mock, reg, 42.0, result, max_attempts=2)

        assert servo_mock.write.call_count == 2
        assert len(result.restored) == 0
        assert len(result.failed) == 1
        failed_reg, failed_value, failed_exc = result.failed[0]
        assert failed_reg is reg
        assert failed_value == 42.0
        assert isinstance(failed_exc, RuntimeError)

    def test_restore_skips_when_no_baseline_value(self, mocker: MockerFixture):
        """restore() skips registers with no baseline entry."""
        servo_mock = mocker.MagicMock(spec=Servo)
        reg = Register(dtype=RegDtype.FLOAT, access=RegAccess.RW, identifier="ORPHAN")
        baseline = DriveRegistersValue(OrderedDict())
        session = DriveRegistersSession(
            servo=servo_mock, baseline=baseline, do_not_restore_registers=set()
        )
        session._changes[reg] = 99.0

        result = session.restore()

        servo_mock.write.assert_not_called()
        assert len(result.skipped) == 1
        assert result.skipped[0] == (reg, "No baseline value")

    def test_restore_skips_unchanged_values(self, mocker: MockerFixture):
        """restore() silently skips registers whose value matches baseline."""
        servo_mock = mocker.MagicMock(spec=Servo)
        reg = Register(dtype=RegDtype.FLOAT, access=RegAccess.RW, identifier="UNCHANGED")
        baseline = DriveRegistersValue(OrderedDict([(reg, 42.0)]))
        session = DriveRegistersSession(
            servo=servo_mock, baseline=baseline, do_not_restore_registers=set()
        )
        session._changes[reg] = 42.0

        result = session.restore()

        servo_mock.write.assert_not_called()
        assert len(result.restored) == 0
        assert len(result.skipped) == 0

    def test_force_restore_no_differences(self, mocker: MockerFixture):
        """force_restore() returns empty result when hardware matches baseline."""
        servo_mock = mocker.MagicMock(spec=Servo)
        reg = Register(dtype=RegDtype.FLOAT, access=RegAccess.RW, identifier="SAME")
        baseline = DriveRegistersValue(OrderedDict([(reg, 42.0)]))
        session = DriveRegistersSession(
            servo=servo_mock, baseline=baseline, do_not_restore_registers=set()
        )

        current_state = DriveRegistersValue(OrderedDict([(reg, 42.0)]))
        mocker.patch.object(
            DriveRegistersValue, "from_hardware", autospec=True, return_value=current_state
        )
        result = session.force_restore()

        servo_mock.write.assert_not_called()
        assert result.all_succeeded
        assert len(result.restored) == 0
        assert len(result.skipped) == 0
        assert len(result.failed) == 0

    def test_reconcile_registers_updates_dirty_register_from_hardware(
        self,
        mocker: MockerFixture,
    ):
        """reconcile_registers() replaces an unknown dirty value with the hardware value."""
        servo_mock = mocker.MagicMock(spec=Servo)
        reg = Register(dtype=RegDtype.FLOAT, access=RegAccess.RW, identifier="DIRTY")
        baseline = DriveRegistersValue(OrderedDict([(reg, 42.0)]))
        session = DriveRegistersSession(
            servo=servo_mock,
            baseline=baseline,
            do_not_restore_registers=set(),
        )
        session._changes[reg] = None

        current_state = DriveRegistersValue(OrderedDict([(reg, 99.0)]))
        mocker.patch.object(
            DriveRegistersValue, "from_hardware", autospec=True, return_value=current_state
        )

        session.reconcile_registers()

        assert session._changes[reg] == 99.0
        assert session.current_value().get(reg) == 99.0

    def test_reset_clears_changes(self, mocker: MockerFixture):
        """reset() clears tracked changes and rebases from the current tracked state."""
        servo_mock = mocker.MagicMock(spec=Servo)
        reg = Register(dtype=RegDtype.FLOAT, access=RegAccess.RW, identifier="TEST_REG")
        baseline = DriveRegistersValue(OrderedDict([(reg, 42.0)]))
        session = DriveRegistersSession(
            servo=servo_mock, baseline=baseline, do_not_restore_registers=set()
        )
        session._changes[reg] = 99.0
        assert len(session._changes) == 1

        session.reset()

        assert len(session._changes) == 0
        assert session.baseline.get(reg) == 99.0

    @pytest.mark.ethernet
    @pytest.mark.ethercat
    @pytest.mark.canopen
    @pytest.mark.virtual
    def test_reset_allows_fresh_tracking(
        self,
        servo: Servo,
    ) -> None:
        """After reset(), subsequent writes are tracked from scratch."""

        baseline = DriveRegistersValue.from_hardware(servo)
        session = DriveRegistersSession(
            servo=servo,
            baseline=baseline,
            do_not_restore_registers=set(),
        )
        session.start()

        previous_value = _read_user_over_voltage_uid(servo)
        new_value = previous_value - 1.0
        servo.write(_USER_OVER_VOLTAGE_UID, new_value, subnode=1)
        assert len(session._changes) >= 1

        session.reset()
        assert len(session._changes) == 0
        assert (
            session.baseline.get(servo.dictionary.get_register(_USER_OVER_VOLTAGE_UID, axis=1))
            == new_value
        )

        # Write again should be tracked
        servo.write(_USER_OVER_VOLTAGE_UID, previous_value, subnode=1)
        assert len(session._changes) >= 1
        session.stop()


class TestTrackObjects:
    """Tests for track_objects parameter on DriveContextManager."""

    @pytest.mark.ethernet
    @pytest.mark.ethercat
    @pytest.mark.canopen
    @pytest.mark.virtual
    def test_track_objects_false_skips_object_read(
        self,
        servo: Servo,
        mocker: MockerFixture,
    ) -> None:
        """track_objects=False skips complete-access object reads and callbacks."""

        store_spy = mocker.patch.object(DriveContextManager, "_store_objects_data", return_value={})
        subscribe_spy = mocker.patch.object(servo, "register_update_complete_access_subscribe")

        context = DriveContextManager(servo, track_objects=False)
        with context:
            store_spy.assert_not_called()
            subscribe_spy.assert_not_called()

    @pytest.mark.ethernet
    @pytest.mark.ethercat
    @pytest.mark.canopen
    @pytest.mark.virtual
    def test_track_objects_true_reads_objects(
        self,
        servo: Servo,
        mocker: MockerFixture,
    ) -> None:
        """track_objects=True (default) reads complete-access objects."""

        subscribe_spy = mocker.patch.object(servo, "register_update_complete_access_subscribe")
        unsubscribe_spy = mocker.patch.object(servo, "register_update_complete_access_unsubscribe")

        context = DriveContextManager(servo, track_objects=True)
        with context:
            subscribe_spy.assert_called_once()
            unsubscribe_spy.assert_not_called()


class TestDirtyMappedPdoRegisters:
    """Tests for dirty tracking of EtherCAT RPDO-mapped registers."""

    @pytest.mark.ethercat
    def test_state_request_marks_rpdo_registers_dirty(
        self,
        servo: EthercatServo,
        net,
    ) -> None:
        """A real PDO exchange marks mapped RPDO registers dirty for restore."""

        rpdo_assign = servo.dictionary.get_register("ETG_COMMS_RPDO_ASSIGN_TOTAL")
        tpdo_assign = servo.dictionary.get_register("ETG_COMMS_TPDO_ASSIGN_TOTAL")

        rpdo_register = servo.dictionary.get_register("CL_POS_SET_POINT_VALUE")
        tpdo_register = servo.dictionary.get_register("CL_POS_FBK_VALUE")
        baseline_value = servo.read(rpdo_register)

        servo.reset_rpdo_mapping()
        servo.reset_tpdo_mapping()

        rpdo_map = RPDOMap()
        rpdo_map.add_registers(rpdo_register)
        rpdo_map.items[0].value = baseline_value
        tpdo_map = TPDOMap()
        tpdo_map.add_registers(tpdo_register)
        servo.set_pdo_map_to_slave([rpdo_map], [tpdo_map])

        context = DriveContextManager(servo, track_objects=False)

        try:
            with context:
                net.start_pdos()
                assert context.changes == {
                    # only the rpdo assign register has been reset to unknown state,
                    # since it is assumed it will constantly change while it's on OP state
                    rpdo_register: None,

                    # The assign index registers have been tracked via regular
                    # register update callbacks too
                    rpdo_assign: 1,  # rpdo assign total register
                    tpdo_assign: 1,  # tpdo assign total register
                    
                }
                assert context.pending_changes is True

            assert context.changes == {}
            assert context.pending_changes is False
            assert servo.read(rpdo_register) == baseline_value
        finally:
            if net.pdo_manager.is_active:
                net.stop_pdos()

    @pytest.mark.ethercat
    def test_state_request_dirty_tracking_can_be_disabled(
        self,
        servo: EthercatServo,
    ) -> None:
        """The dirty-PDO hook can be disabled explicitly."""

        rpdo_register = servo.dictionary.get_register("CL_POS_SET_POINT_VALUE")
        baseline_value = servo.read(rpdo_register)

        servo.reset_rpdo_mapping()
        rpdo_map = RPDOMap()
        rpdo_map.add_registers(rpdo_register)
        servo.set_pdo_map_to_slave([rpdo_map], [])

        session = DriveRegistersSession(
            servo,
            DriveRegistersValue(OrderedDict([(rpdo_register, baseline_value)])),
            set_dirty_mapped_pdo_registers=False,
        )

        servo.request_node_state(SlaveState.OP_STATE)

        assert session.changes == {}


class TestPendingChanges:
    """Tests for DriveContextManager.pending_changes property."""

    def test_pending_changes_false_without_session(self, mocker: MockerFixture):
        """pending_changes is False before __enter__ (no session)."""
        servo_mock = mocker.MagicMock(spec=Servo)
        context = DriveContextManager(servo_mock, track_objects=False)

        assert context.pending_changes is False

    def test_pending_changes_true_with_tracked_register(self, mocker: MockerFixture):
        """pending_changes is True when a register change is tracked."""
        servo_mock = mocker.MagicMock(spec=Servo)
        reg = Register(dtype=RegDtype.FLOAT, access=RegAccess.RW, identifier="TEST_REG")
        baseline = DriveRegistersValue(OrderedDict([(reg, 42.0)]))
        context = DriveContextManager(servo_mock, baseline=baseline, track_objects=False)
        context.__enter__()

        assert context.pending_changes is False

        context._session._changes[reg] = 99.0
        assert context.pending_changes is True

        context.__exit__(None, None, None)

    def test_pending_changes_true_with_tracked_object(self, mocker: MockerFixture):
        """pending_changes is True when only an object change is tracked."""
        servo_mock = mocker.MagicMock(spec=Servo)
        baseline = DriveRegistersValue(OrderedDict())
        context = DriveContextManager(servo_mock, baseline=baseline, track_objects=False)
        context.__enter__()

        context._objects_changed[mocker.MagicMock()] = b""
        assert context.pending_changes is True

        context.__exit__(None, None, None)


class TestContextManagerReset:
    """Tests for DriveContextManager.reset() method."""

    def test_reset_tracked_clears_session_changes(self, mocker: MockerFixture):
        """reset(force=False) restores tracked changes, clears them, and rebuilds session."""
        servo_mock = mocker.MagicMock(spec=Servo)

        reg = Register(dtype=RegDtype.FLOAT, access=RegAccess.RW, identifier="TEST_REG")
        baseline = DriveRegistersValue(OrderedDict([(reg, 42.0)]))

        context = DriveContextManager(servo_mock, baseline=baseline, track_objects=False)
        context.__enter__()

        baseline_id = id(context._baseline)

        # Simulate a change
        context._session._changes[reg] = 99.0
        assert len(context._session._changes) == 1

        # Reset
        context.reset(force=False)

        # Session should be rebuilt with cleared changes
        assert len(context._session._changes) == 0
        # Baseline should not change
        assert id(context._baseline) == baseline_id

        context.__exit__(None, None, None)

    @pytest.mark.ethernet
    @pytest.mark.ethercat
    @pytest.mark.canopen
    @pytest.mark.virtual
    def test_reset_tracked_restores_to_baseline_integration(self, servo: "Servo"):
        """reset(force=False) restores tracked changes and clears tracking twice."""
        context = DriveContextManager(servo)

        with context:
            baseline_id = id(context._baseline)
            objects_id = id(context._original_canopen_object_values)

            # Write a value
            previous_value = _read_user_over_voltage_uid(servo)
            new_value = previous_value + 1.0
            servo.write(_USER_OVER_VOLTAGE_UID, new_value, subnode=1)
            assert _read_user_over_voltage_uid(servo) == new_value

            # Reset (tracked mode)
            context.reset(force=False)

            # Should be restored to original value
            assert _read_user_over_voltage_uid(servo) == previous_value
            # Baseline and objects should be unchanged
            assert id(context._baseline) == baseline_id
            assert id(context._original_canopen_object_values) == objects_id

            # Write again and reset again
            new_value_2 = previous_value + 2.0
            servo.write(_USER_OVER_VOLTAGE_UID, new_value_2, subnode=1)
            assert _read_user_over_voltage_uid(servo) == new_value_2

            # Reset again
            context.reset(force=False)

            # Should be restored again
            assert _read_user_over_voltage_uid(servo) == previous_value
            # Baseline and objects should still be unchanged
            assert id(context._baseline) == baseline_id
            assert id(context._original_canopen_object_values) == objects_id

    def test_reset_force_mode_with_mocks(self, mocker: MockerFixture):
        """reset(force=True) calls force_restore on session."""
        servo_mock = mocker.MagicMock(spec=Servo)
        servo_mock.register_update_subscribe = mocker.MagicMock()
        servo_mock.register_update_unsubscribe = mocker.MagicMock()
        servo_mock.register_update_complete_access_subscribe = mocker.MagicMock()
        servo_mock.register_update_complete_access_unsubscribe = mocker.MagicMock()

        reg = Register(dtype=RegDtype.FLOAT, access=RegAccess.RW, identifier="TEST_REG")
        baseline = DriveRegistersValue(OrderedDict([(reg, 42.0)]))

        context = DriveContextManager(servo_mock, baseline=baseline, track_objects=False)
        context.__enter__()

        baseline_id = id(context._baseline)

        # Simulate a change
        context._session._changes[reg] = 99.0

        # Mock force_restore to avoid calling from_hardware
        force_restore_spy = mocker.patch.object(
            context._session, "force_restore", return_value=RestoreResult()
        )

        # Reset in force mode
        context.reset(force=True)

        # force_restore should have been called
        force_restore_spy.assert_called_once()
        # Baseline should not change
        assert id(context._baseline) == baseline_id
        # Session should be rebuilt
        assert len(context._session._changes) == 0

        context.__exit__(None, None, None)

    def test_force_restore_skips_session_when_registers_disabled(self, mocker: MockerFixture):
        """force_restore(restore_registers=False) does not touch the session."""
        servo_mock = mocker.MagicMock(spec=Servo)
        servo_mock.register_update_subscribe = mocker.MagicMock()
        servo_mock.register_update_unsubscribe = mocker.MagicMock()
        servo_mock.register_update_complete_access_subscribe = mocker.MagicMock()
        servo_mock.register_update_complete_access_unsubscribe = mocker.MagicMock()

        reg = Register(dtype=RegDtype.FLOAT, access=RegAccess.RW, identifier="TEST_REG")
        baseline = DriveRegistersValue(OrderedDict([(reg, 42.0)]))

        context = DriveContextManager(servo_mock, baseline=baseline, track_objects=False)
        context.__enter__()
        spy = mocker.patch.object(context._session, "force_restore", return_value=RestoreResult())

        context.force_restore(restore_registers=False, restore_objects=False)

        spy.assert_not_called()

        context.__exit__(None, None, None)
