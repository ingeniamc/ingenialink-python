import pytest

from ingenialink.dictionary_deprecated import Dictionary


@pytest.mark.ethercat
def test_dictionary(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    assert isinstance(servo.dictionary, Dictionary)

    assert servo.dictionary.path is not None
    assert servo.dictionary.version is not None
    assert servo.dictionary.firmware_version is not None
    assert servo.dictionary.revision_number is not None
    assert servo.dictionary.product_code is not None
    assert servo.dictionary.interface is not None
    assert servo.dictionary.part_number is not None
    assert servo.dictionary.subnodes is not None
    assert servo.dictionary.errors is not None
    assert servo.dictionary.categories is not None
    assert servo.dictionary.registers(0) is not None
    assert servo.dictionary.registers(1) is not None
