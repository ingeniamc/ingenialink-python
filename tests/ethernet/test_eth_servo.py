import pytest
import os


@pytest.mark.ethernet
def test_save_configuration(connect_ethernet):
    servo, net = connect_ethernet
    assert servo is not None and net is not None

    filename = "resources/configurations/eth_config.xcf"

    r = servo.save_configuration(filename)
    assert r >= 0

    if os.path.isfile(filename):
        os.remove(filename)


@pytest.mark.ethernet
def test_load_configuration(connect_ethernet):
    servo, net = connect_ethernet
    assert servo is not None and net is not None

    r = servo.load_configuration("resources/configurations/eve-xcr-e_1.8.1_cfg.xcf")
    assert r >= 0


@pytest.mark.ethernet
def test_store_parameters(connect_ethernet):
    servo, net = connect_ethernet
    assert servo is not None and net is not None

    servo.store_parameters()


@pytest.mark.ethernet
def test_restore_parameters(connect_ethernet):
    servo, net = connect_ethernet
    assert servo is not None and net is not None

    servo.restore_parameters()


