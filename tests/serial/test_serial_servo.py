import pytest
import os


@pytest.mark.serial
def test_save_configuration(connect_serial):
    servo, net = connect_serial
    assert servo is not None and net is not None

    filename = "resources/configurations/ser_config.xcf"

    servo.save_configuration(filename)

    if os.path.isfile(filename):
        os.remove(filename)


@pytest.mark.serial
def test_load_configuration(connect_serial):
    servo, net = connect_serial
    assert servo is not None and net is not None

    servo.load_configuration("resources/configurations/eve-xcr-e_1.8.1_cfg.xcf")


@pytest.mark.serial
def test_store_parameters(connect_serial):
    servo, net = connect_serial
    assert servo is not None and net is not None

    servo.store_parameters()


@pytest.mark.serial
def test_restore_parameters(connect_serial):
    servo, net = connect_serial
    assert servo is not None and net is not None

    servo.restore_parameters()


