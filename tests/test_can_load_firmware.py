import pytest


def test_load_firmware(connect_canopen):
    servo, net = connect_canopen
    assert servo is not None and net is not None

    net.load_firmware(32, 'eve-net-c_1.8.1.sfu')
