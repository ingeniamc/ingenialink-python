import pytest

from ingenialink.ethernet.eth_net import EthernetNetwork


def test_store(connect_ethernet):
    servo, net = connect_ethernet()
    assert servo is not None and net is not None

    servo.store_parameters(subnode=1)


def test_restore(connect_ethernet):
    servo, net = connect_ethernet()
    assert servo is not None and net is not None

    servo.restore_parameters()

