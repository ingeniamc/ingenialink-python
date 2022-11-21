import pytest

from ingenialink.canopen.network import CanopenNetwork, CAN_DEVICE, CAN_BAUDRATE

@pytest.mark.canopen
def test_connect_to_slave(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None
    assert len(net.servos) == 1
    fw_version = servo.read('DRV_ID_SOFTWARE_VERSION')
    assert fw_version is not None and fw_version != ''


@pytest.mark.canopen
def test_scan_slaves(read_config):
    net = CanopenNetwork(device=CAN_DEVICE(read_config['canopen']['device']),
                         channel=read_config['canopen']['channel'],
                         baudrate=CAN_BAUDRATE(read_config['canopen']['baudrate']))
    slaves = net.scan_slaves()
    assert len(slaves) > 0

