import pytest
from ingenialink.serial.network import SerialNetwork


@pytest.mark.serial
def test_connect_to_slave():
    net = SerialNetwork()
    servo = net.connect_to_slave(
        "COM5",
        "resources/dictionaries/eve-core_1.8.1.xdf")

    assert servo is not None

    net.disconnect_from_slave(servo)
    assert len(net.servos) == 0


@pytest.mark.serial
def test_scan_slaves():
    net = SerialNetwork()
    servos = net.scan_slaves()

    assert len(servos) > 0
