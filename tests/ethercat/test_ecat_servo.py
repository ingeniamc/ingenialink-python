import pytest
import os


@pytest.mark.ethercat
def test_save_configuration(connect_ethercat):
    servo, net = connect_ethercat
    assert servo is not None and net is not None

    filename = "resources/configurations/ecat_config.xcf"

    r = servo.save_configuration(filename)
    assert r >= 0

    if os.path.isfile(filename):
        os.remove(filename)


@pytest.mark.ethercat
def test_load_configuration(connect_ethercat):
    servo, net = connect_ethercat
    assert servo is not None and net is not None

    r = servo.load_configuration("resources/configurations/eve-xcr-e_1.8.1_cfg.xcf")
    assert r >= 0


@pytest.mark.ethercat
def test_store_parameters(connect_ethercat):
    servo, net = connect_ethercat
    assert servo is not None and net is not None

    servo.store_parameters()


@pytest.mark.ethercat
def test_restore_parameters(connect_ethercat):
    servo, net = connect_ethercat
    assert servo is not None and net is not None

    servo.restore_parameters()


