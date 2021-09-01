import pytest

from ingenialink.ethernet.network import EthernetNetwork


@pytest.mark.ethernet
def test_connect_to_slave():
    net = EthernetNetwork()
    servo = net.connect_to_slave("192.168.2.22",
                                 "resources/dictionaries/eve-xcr-e_eoe_1.8.1.xdf")
    assert servo is not None

    net.disconnect_from_slave(servo)
    assert len(net.servos) == 0
