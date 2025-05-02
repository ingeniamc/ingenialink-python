import pytest

from ingenialink.drive_context_manager import DriveContextManager

_USER_OVER_VOLTAGE_UID = "DRV_PROT_USER_OVER_VOLT"


def _read_user_over_voltage_uid(servo):
    return servo.read(_USER_OVER_VOLTAGE_UID, subnode=1)


@pytest.mark.smoke
@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_drive_context_manager(connect_to_slave):
    servo, _ = connect_to_slave
    context = DriveContextManager(servo)

    new_reg_value = 100.0
    previous_reg_value = _read_user_over_voltage_uid(servo)
    assert previous_reg_value != new_reg_value

    with context:
        servo.write(_USER_OVER_VOLTAGE_UID, new_reg_value, subnode=1)
        assert _read_user_over_voltage_uid(servo) == new_reg_value

    assert _read_user_over_voltage_uid(servo) == previous_reg_value
