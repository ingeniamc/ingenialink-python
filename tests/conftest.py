import pytest

from ingenialink.net import NET_TRANS_PROT
from ingenialink.canopen.netwrok import CanopenNetwork, CAN_DEVICE, CAN_BAUDRATE
from ingenialink.ethernet.network import EthernetNetwork


@pytest.fixture
def connect_canopen():
    net = CanopenNetwork(device=CAN_DEVICE.IXXAT,
                         channel=0,
                         baudrate=CAN_BAUDRATE.Baudrate_1M)

    servo = net.connect_to_slave(target=32,
                                 dictionary='resources/eve-net-c_can_1.8.1.xdf',
                                 eds='resources/eve-net-c_1.8.1.eds')
    yield servo, net

    net.disconnect_from_slave(servo)


@pytest.fixture
def connect_ethernet():
    net = EthernetNetwork()
    servo = net.connect_to_slave(
        "192.168.2.22",
        "resources/eve-net-c_eth_1.8.1.xdf",
        1061,
        NET_TRANS_PROT.UDP)

    yield servo, net

    net.disconnect_from_slave(servo)
