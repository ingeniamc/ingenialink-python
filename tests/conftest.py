import pytest

from ingenialink.canopen.can_net import CanopenNetwork, CAN_DEVICE, CAN_BAUDRATE


@pytest.fixture
def connect_canopen():
    net = CanopenNetwork(device=CAN_DEVICE.IXXAT,
                         channel=0,
                         baudrate=CAN_BAUDRATE.Baudrate_1M)

    servo = net.connect_to_slave(target=32,
                                 dictionary='resources/eve-net-c_can_1.8.1.xdf',
                                 eds='resources/eve-net-c_1.8.1.eds')
    yield servo, net
