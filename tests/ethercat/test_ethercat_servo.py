import pytest

from ingenialink.exceptions import ILStateError


@pytest.mark.ethercat
def test_emcy_callback(mocker, connect_to_slave):
    servo, _ = connect_to_slave
    mocked = mocker.patch("ingenialink.ethercat.servo.EthercatServo.get_emergency_description")
    prev_val = servo.read("DRV_PROT_USER_OVER_VOLT", subnode=1)
    servo.write("DRV_PROT_USER_OVER_VOLT", data=10.0, subnode=1)
    with pytest.raises(ILStateError):
        servo.enable()
    servo.fault_reset()
    assert mocked.call_count == 2
    servo.write("DRV_PROT_USER_OVER_VOLT", data=prev_val, subnode=1)
