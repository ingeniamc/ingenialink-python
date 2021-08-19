import pytest
import os


@pytest.mark.ethernet
def test_load_configuration(connect_ethernet):
    servo, net = connect_ethernet()
    assert servo is not None and net is not None

    r = servo.load_configuration("resources/eve-xcr-e_1.8.1_cfg.xcf")
    assert r >= 0


@pytest.mark.ethernet
def test_save_configuration(connect_ethernet):
    servo, net = connect_ethernet()
    assert servo is not None and net is not None

    # Remove possible already saved output configuration
    try:
        os.remove("resources/output_cfg.xcf")
    except:
        pass
    r = servo.save_configuration("resources/output_cfg.xcf")
    assert r >= 0


@pytest.mark.ethernet
def test_store_parameters(connect_ethernet):
    servo, net = connect_ethernet()
    assert servo is not None and net is not None

    servo.store_parameters(subnode=1)


@pytest.mark.ethernet
def test_restore_parameters(connect_ethernet):
    servo, net = connect_ethernet()
    assert servo is not None and net is not None

    servo.restore_parameters()


