import sys

import ingenialink as il
from ingenialink.ethernet.eth_net import EthernetNetwork


def connection_example():
    net = EthernetNetwork()
    servo = net.connect_to_slave("192.168.2.22",
                                 "eve-net-c_eth_1.8.1.xdf",
                                 1061,
                                 il.net.NET_TRANS_PROT.UDP)

    print(servo.read('DRV_ID_SOFTWARE_VERSION'))

    net.disconnect_from_slave(servo)


if __name__ == '__main__':
    connection_example()
    sys.exit(0)
