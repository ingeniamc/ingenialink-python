import pytest

from ingenialink.ethercat.servo import EthercatServo
from ingenialink.exceptions import ILError

EVEREST_PROJECT_NUMBER = 44


class EmcyTest:
    def __init__(self):
        self.messages = []

    def emcy_callback(self, emcy_msg):
        self.messages.append(emcy_msg)


def is_coco_moco(servo):
    product_code = servo.read("DRV_ID_PRODUCT_CODE")
    return product_code >> 20 == EVEREST_PROJECT_NUMBER


@pytest.mark.canopen()
@pytest.mark.ethercat()
def test_emcy_callback(connect_to_slave):
    servo, _ = connect_to_slave
    if isinstance(servo, EthercatServo) and is_coco_moco(servo):
        pytest.skip("The test is not supported for COCO MOCO EtherCAT drives")
    emcy_test = EmcyTest()
    servo.emcy_subscribe(emcy_test.emcy_callback)
    prev_val = servo.read("DRV_PROT_USER_OVER_VOLT", subnode=1)
    servo.write("DRV_PROT_USER_OVER_VOLT", data=10.0, subnode=1)
    with pytest.raises(ILError):
        servo.enable()
    servo.fault_reset()
    assert len(emcy_test.messages) == 2
    first_emcy = emcy_test.messages[0]
    assert first_emcy.error_code == 0x3231
    assert first_emcy.get_desc() == "User Over-voltage detected"
    second_emcy = emcy_test.messages[1]
    assert second_emcy.error_code == 0x0000
    assert second_emcy.get_desc() == "No error"
    servo.write("DRV_PROT_USER_OVER_VOLT", data=prev_val, subnode=1)
    servo.emcy_unsubscribe(emcy_test.emcy_callback)


@pytest.mark.ethercat()
def test_emcy_callback_coco_moco_ethercat(connect_to_slave):
    # EMCY test for COCO MOCO EtherCAT drives
    # Check INGK-993
    servo, _ = connect_to_slave
    if not is_coco_moco(servo):
        pytest.skip("The test is only for COCO MOCO EtherCAT drives")
    emcy_test = EmcyTest()
    servo.emcy_subscribe(emcy_test.emcy_callback)
    prev_val = servo.read("DRV_PROT_USER_OVER_VOLT", subnode=1)
    servo.write("DRV_PROT_USER_OVER_VOLT", data=10.0, subnode=1)
    with pytest.raises(ILError):
        servo.enable()
    try:
        servo.fault_reset()
    except ILError:
        servo.fault_reset()
    assert len(emcy_test.messages) > 0
    servo.write("DRV_PROT_USER_OVER_VOLT", data=prev_val, subnode=1)
    servo.emcy_unsubscribe(emcy_test.emcy_callback)
