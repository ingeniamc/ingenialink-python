import pytest

from ingenialink.exceptions import ILStateError


class EmcyTest:
    def emcy_test(emcy_msg):
        pass


@pytest.mark.canopen
@pytest.mark.ethercat
def test_emcy_callback(mocker, connect_to_slave):
    servo, _ = connect_to_slave
    mocked = mocker.patch.object(EmcyTest, "emcy_test")
    servo.emcy_subscribe(EmcyTest.emcy_test)
    prev_val = servo.read("DRV_PROT_USER_OVER_VOLT", subnode=1)
    servo.write("DRV_PROT_USER_OVER_VOLT", data=10.0, subnode=1)
    with pytest.raises(ILStateError):
        servo.enable()
    servo.fault_reset()
    assert mocked.call_count == 2
    servo.write("DRV_PROT_USER_OVER_VOLT", data=prev_val, subnode=1)
    servo.emcy_unsubscribe(EmcyTest.emcy_test)
