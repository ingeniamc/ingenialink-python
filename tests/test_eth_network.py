import pytest

from ingenialink.ethernet.eth_net import EthernetNetwork


def test_connect():
    network = EthernetNetwork("192.168.2.22", "resources/eve-xcr-e_eoe_1.8.1.xdf", 1061, 2)
    r, servo = network.connect()
    assert (servo is not None) and (r >= 0)
