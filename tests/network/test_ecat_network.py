import pytest

from ingenialink.ethercat.network import EthercatNetwork


@pytest.mark.ethercat
def test_scan_slaves(read_config):
    net = EthercatNetwork(read_config['ethercat']['ifname'])

    slaves = net.scan_slaves()
    assert len(slaves) > 0
