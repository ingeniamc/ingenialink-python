import pytest

from ingenialink.canopen.network import CanopenNetwork, CAN_DEVICE, CAN_BAUDRATE


@pytest.mark.canopen
def test_scan_slaves():
    net = CanopenNetwork(device=CAN_DEVICE.IXXAT,
                         channel=0,
                         baudrate=CAN_BAUDRATE.Baudrate_1M)
    slaves = net.scan_slaves()
    assert len(slaves) > 0


@pytest.mark.canopen
def test_connect_to_slave():
    net = CanopenNetwork(device=CAN_DEVICE.IXXAT,
                         channel=0,
                         baudrate=CAN_BAUDRATE.Baudrate_1M)

    servo = net.connect_to_slave(
        target=32,
        dictionary='resources/dictionaries/eve-net-c_can_1.8.1.xdf',
        eds='resources/dictionaries/eve-net-c_1.8.1.eds')
    assert servo is not None

    fw_version = servo.read('DRV_ID_SOFTWARE_VERSION')
    assert fw_version is not None and fw_version != ''

    net.disconnect_from_slave(servo)
    assert len(net.servos) == 0
