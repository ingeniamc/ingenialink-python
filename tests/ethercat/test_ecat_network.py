import pytest

from ingenialink.ethercat.network import EthercatNetwork


@pytest.mark.ethercat
def test_scan_slaves():
    net = EthercatNetwork("\\Device\\NPF_{192D1D2F-C684-467D-A637-EC07BD434A63}")

    slaves = net.scan_slaves()
    assert len(slaves) > 0


@pytest.mark.ethercat
def test_connect_to_slave():
    net = EthercatNetwork("\\Device\\NPF_{192D1D2F-C684-467D-A637-EC07BD434A63}")

    servo = net.connect_to_slave(
        target=1,
        dictionary='resources/dictionaries/eve-xcr-e_eoe_1.8.1.xdf'
    )

    assert servo is not None

    net.disconnect_from_slave(servo)
    assert len(net.servos) == 0
