import time

import pytest

from ingenialink.constants import PASSWORD_STORE_ALL
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

    # If not additional ignored registers are added,
    # the default ones are the ones that are troublesome
    # because they have a specific password, that is written but not read.
    assert context._do_not_restore_registers == {
        servo.STORE_COCO_ALL,
        servo.STORE_MOCO_ALL_REGISTERS,
        servo.RESTORE_COCO_ALL,
        servo.RESTORE_MOCO_ALL_REGISTERS,
    }

    servo.write(servo.CONTROL_WORD_REGISTERS, 10)

    servo_write_spy = mocker.spy(context.drive, "write")

    with context:
        # One of this registers is picked as a sample to write
        servo.write(servo.STORE_COCO_ALL, PASSWORD_STORE_ALL, subnode=0)
        # Inside the context, to write is called
        assert servo_write_spy.call_count == 1

        # Some drives are unresponsive while they are doing the store/restore
        # Wait some time
        time.sleep(8)
        # https://novantamotion.atlassian.net/browse/INGK-1106

        # Other registers that are not ignored are expected to be rolled back
        servo.write(servo.CONTROL_WORD_REGISTERS, 0)
        assert servo_write_spy.call_count == 2

        servo_write_spy.reset_mock()

    # After exiting the context, this register is not restored.
    # No write has been called to restore the register.
    assert servo_write_spy.call_count == 1
    assert servo_write_spy.call_args[0][0] == servo.CONTROL_WORD_REGISTERS
    assert servo_write_spy.call_args[0][1] == 10

    assert servo.read(servo.CONTROL_WORD_REGISTERS) == 10


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
