import pytest

from ingenialink.ethernet.eth_net import EthernetNetwork


def test_connect():
    network = EthernetNetwork()
    servo = network.connect_to_slave("192.168.2.22",
                                     "resources/eve-xcr-e_eoe_1.8.1.xdf")
    assert (servo is not None)
