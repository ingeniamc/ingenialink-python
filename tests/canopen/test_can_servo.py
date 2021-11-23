import os
import pytest


@pytest.mark.canopen
def test_save_configuration(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    filename = 'resources/configurations/can_config.xcf'

    servo.save_configuration(filename)

    assert os.path.isfile(filename)

    if os.path.isfile(filename):
        os.remove(filename)


@pytest.mark.canopen
def test_load_configuration(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    filename = 'resources/configurations/canopen-config.xcf'

    assert os.path.isfile(filename)

    servo.load_configuration(filename)


@pytest.mark.canopen
def test_store_parameters(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    servo.store_parameters()


@pytest.mark.canopen
def test_restore_parameters(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    servo.restore_parameters()
