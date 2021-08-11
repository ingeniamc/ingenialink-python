import pytest

from ingenialink.canopen.network import CanopenNetwork, CAN_DEVICE, CAN_BAUDRATE


def test_scan():
    net = CanopenNetwork(device=CAN_DEVICE.IXXAT,
                         channel=0,
                         baudrate=CAN_BAUDRATE.Baudrate_1M)
    nodes = net.scan_slaves()
    assert len(nodes) > 0


def test_connect():
    net = CanopenNetwork(device=CAN_DEVICE.IXXAT,
                         channel=0,
                         baudrate=CAN_BAUDRATE.Baudrate_1M)

    servo = net.connect_to_slave(target=32,
                                 dictionary='resources/eve-net-c_can_1.8.1.xdf',
                                 eds='resources/eve-net-c_1.8.1.eds')
    assert servo is not None

    fw_version = servo.read('DRV_ID_SOFTWARE_VERSION')
    assert fw_version is not None and fw_version != ''

    net.disconnect_from_slave(servo)
    assert len(net.servos) == 0
