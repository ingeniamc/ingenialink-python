from typing import Optional

import pytest

from ingenialink.constants import (
    PASSWORD_RESTORE_ALL,
    PASSWORD_STORE_ALL,
    PASSWORD_STORE_RESTORE_SUB_0,
)
from ingenialink.drive_context_manager import DriveContextManager

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
def test_drive_context_manager(setup_manager):
    servo, _, _, _ = setup_manager
    context = DriveContextManager(servo)

    new_reg_value = 100.0
    previous_reg_value = _read_user_over_voltage_uid(servo)
    if previous_reg_value == new_reg_value:
        new_reg_value -= 1.0

    with context:
        servo.write(_USER_OVER_VOLTAGE_UID, new_reg_value, subnode=1)
        assert _read_user_over_voltage_uid(servo) == new_reg_value

    assert _read_user_over_voltage_uid(servo) == previous_reg_value


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_drive_context_manager_nested_contexts(setup_manager):
    servo, _, _, _ = setup_manager
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
def test_drive_context_manager_skips_default_do_not_restore_registers(mocker, setup_manager):
    servo, _, _, _ = setup_manager
    context = DriveContextManager(servo)
    assert len(context._do_not_restore_registers) == 4

    register_update_callback_spy = mocker.spy(context, "_register_update_callback")
    servo_write_spy = mocker.spy(context.drive, "write")

    def assert_store_restore_is_skipped(
        store: bool,
        subnode: Optional[int],
        expected_uid: str,
        expected_value: int,
        prev_call_count: int,
    ) -> int:
        if store:
            servo.store_parameters(subnode=subnode)
        else:
            servo.restore_parameters(subnode=subnode)
        call_count = register_update_callback_spy.call_count
        assert call_count > prev_call_count
        call_args = register_update_callback_spy.call_args.args
        call_args[1].identifier == expected_uid
        call_args[2] == expected_value
        assert context._registers_changed == {}
        return call_count

    with context:
        prev_call_count = register_update_callback_spy.call_count
        prev_call_count = assert_store_restore_is_skipped(
            True, 0, servo.STORE_COCO_ALL, PASSWORD_STORE_RESTORE_SUB_0, prev_call_count
        )

        prev_call_count = assert_store_restore_is_skipped(
            True, 1, servo.STORE_MOCO_ALL_REGISTERS, PASSWORD_STORE_ALL, prev_call_count
        )

        prev_call_count = assert_store_restore_is_skipped(
            True, None, servo.STORE_COCO_ALL, PASSWORD_RESTORE_ALL, prev_call_count
        )

        prev_call_count = assert_store_restore_is_skipped(
            False, 0, servo.RESTORE_COCO_ALL, PASSWORD_STORE_RESTORE_SUB_0, prev_call_count
        )

        prev_call_count = assert_store_restore_is_skipped(
            False, 1, servo.RESTORE_MOCO_ALL_REGISTERS, PASSWORD_RESTORE_ALL, prev_call_count
        )

        prev_call_count = assert_store_restore_is_skipped(
            False, None, servo.RESTORE_COCO_ALL, PASSWORD_RESTORE_ALL, prev_call_count
        )

        assert servo_write_spy.call_count == prev_call_count

    # Nothing is restored when the context exits
    assert servo_write_spy.call_count == prev_call_count


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_drive_context_manager_with_do_not_restore_registers(setup_manager):
    servo, _, _, _ = setup_manager
    context = DriveContextManager(servo, do_not_restore_registers=[_USER_OVER_VOLTAGE_UID])
    assert (
        len(context._do_not_restore_registers) == 5
    )  # COCO-MOCO store/restore registers + _USER_OVER_VOLTAGE_UID

    new_reg_value = 100.0
    previous_reg_value = _read_user_over_voltage_uid(servo)
    if previous_reg_value == new_reg_value:
        new_reg_value -= 1.0

    with context:
        servo.write(_USER_OVER_VOLTAGE_UID, new_reg_value, subnode=1)
        assert _read_user_over_voltage_uid(servo) == new_reg_value

    assert _read_user_over_voltage_uid(servo) == new_reg_value
