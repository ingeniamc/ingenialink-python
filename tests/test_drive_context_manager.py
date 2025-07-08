import pytest

from ingenialink.drive_context_manager import DriveContextManager
from ingenialink.ethernet.servo import EthernetServo

_USER_OVER_VOLTAGE_UID = "DRV_PROT_USER_OVER_VOLT"
_USER_UNDER_VOLTAGE_UID = "DRV_PROT_USER_UNDER_VOLT"


def _read_user_over_voltage_uid(servo):
    return servo.read(_USER_OVER_VOLTAGE_UID, subnode=1)


def _read_user_under_voltage_uid(servo):
    return servo.read(_USER_UNDER_VOLTAGE_UID, subnode=1)


def _get_expected_do_not_restore_registers(servo):
    expected_do_not_restore_registers = [
        servo.STORE_COCO_ALL,
        servo.STORE_MOCO_ALL_REGISTERS,
        servo.RESTORE_COCO_ALL,
        servo.RESTORE_MOCO_ALL_REGISTERS,
    ]
    if isinstance(servo, EthernetServo):
        expected_do_not_restore_registers.append(servo.COMMS_ETH_MAC)
    return expected_do_not_restore_registers


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
def test_drive_context_manager_skips_default_do_not_restore_registers(setup_manager):
    servo, _, _, _ = setup_manager
    context = DriveContextManager(servo)

    expected_do_not_restore_registers = _get_expected_do_not_restore_registers(servo)

    assert len(context._do_not_restore_registers) == len(expected_do_not_restore_registers)

    # If not additional ignored registers are added,
    # the default ones are the ones that are troublesome
    # because they have a specific password, that is written but not read.
    assert context._do_not_restore_registers == set(expected_do_not_restore_registers)


@pytest.mark.ethernet
@pytest.mark.ethercat
@pytest.mark.canopen
@pytest.mark.virtual
def test_drive_context_manager_with_do_not_restore_registers(setup_manager):
    servo, _, _, _ = setup_manager
    context = DriveContextManager(servo, do_not_restore_registers=[_USER_OVER_VOLTAGE_UID])
    expected_do_not_restore_registers = _get_expected_do_not_restore_registers(servo)

    assert (
        len(context._do_not_restore_registers) == expected_do_not_restore_registers + 1
    )  # COCO-MOCO store/restore registers + _USER_OVER_VOLTAGE_UID

    new_reg_value = 100.0
    previous_reg_value = _read_user_over_voltage_uid(servo)
    if previous_reg_value == new_reg_value:
        new_reg_value -= 1.0

    with context:
        servo.write(_USER_OVER_VOLTAGE_UID, new_reg_value, subnode=1)
        assert _read_user_over_voltage_uid(servo) == new_reg_value

    assert _read_user_over_voltage_uid(servo) == new_reg_value
