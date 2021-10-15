import pytest

from ingenialink.serial.network import SerialNetwork


@pytest.mark.serial
def test_scan_slaves():
    net = SerialNetwork()
    servos = net.scan_slaves()

    assert len(servos) > 0
