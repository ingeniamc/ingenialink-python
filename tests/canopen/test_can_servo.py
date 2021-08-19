import os
import pytest


@pytest.mark.canopen
def test_save_configuration(connect_canopen):
    servo, net = connect_canopen
    assert servo is not None and net is not None

    filename = 'eve-net-c_1.8.1_canopen.xcf'

    servo.save_configuration(filename, subnode=0)

    assert os.path.isfile(filename)

    if os.path.isfile(filename):
        os.remove(filename)


@pytest.mark.canopen
def test_load_configuration(connect_canopen):
    servo, net = connect_canopen
    assert servo is not None and net is not None

    filename = 'resources/configurations/eve-net-c_1.8.1_canopen.xcf'

    assert os.path.isfile(filename)

    servo.load_configuration(filename, subnode=0)


@pytest.mark.canopen
def test_store_parameters(connect_canopen):
    servo, net = connect_canopen
    assert servo is not None and net is not None

    servo.store_parameters()


@pytest.mark.canopen
def test_restore_parameters(connect_canopen):
    servo, net = connect_canopen
    assert servo is not None and net is not None

    servo.restore_parameters()
