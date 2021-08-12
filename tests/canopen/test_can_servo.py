import os
import pytest


def test_save_configuration(connect_canopen):
    servo, net = connect_canopen
    assert servo is not None and net is not None

    filename = '../can_config.xcf'

    if os.path.isfile(filename):
        os.remove(filename)

    servo.save_configuration(filename, subnode=0)

    assert os.path.isfile(filename)


def test_load_configuration(connect_canopen):
    servo, net = connect_canopen
    assert servo is not None and net is not None

    filename = '../can_config.xcf'

    assert os.path.isfile(filename)

    servo.load_configuration(filename, subnode=0)


def test_store_parameters(connect_canopen):
    servo, net = connect_canopen
    assert servo is not None and net is not None

    servo.store_parameters()


def test_restore_parameters(connect_canopen):
    servo, net = connect_canopen
    assert servo is not None and net is not None

    servo.restore_parameters()
