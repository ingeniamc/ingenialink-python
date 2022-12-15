import pytest

from ingenialink.canopen.network import CanopenNetwork, CAN_DEVICE, CAN_BAUDRATE


@pytest.mark.canopen
def test_scan_slaves(read_config):
    net = CanopenNetwork(
        device=CAN_DEVICE(read_config["canopen"]["device"]),
        channel=read_config["canopen"]["channel"],
        baudrate=CAN_BAUDRATE(read_config["canopen"]["baudrate"]),
    )
    slaves = net.scan_slaves()
    assert len(slaves) > 0
