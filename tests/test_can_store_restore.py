import pytest


def test_store(connect_canopen):
    servo, net = connect_canopen
    assert servo is not None and net is not None

    servo.store_parameters()


def test_restore(connect_canopen):
    servo, net = connect_canopen
    assert servo is not None and net is not None

    servo.restore_parameters()
