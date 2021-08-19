import pytest
from ingenialink.serial.network import SerialNetwork


@pytest.mark.serial
def test_connect_to_slave():
    network = SerialNetwork()
    servo = network.connect_to_slave("COM5",
                                     "../../resources/dictionaries/"
                                     "eve-core_1.8.1.xdf")

    assert (servo is not None)


@pytest.mark.serial
def test_scan_slaves():
    network = SerialNetwork()
    servos = network.scan_slaves()

    assert (len(servos) > 0)
