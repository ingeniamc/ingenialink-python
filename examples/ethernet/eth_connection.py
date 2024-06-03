import sys

from ingenialink.ethernet.network import EthernetNetwork


def connection_example() -> None:
    net = EthernetNetwork()
    servo = net.connect_to_slave("192.168.2.22",
                                 "../../resources/dictionaries/eve-net-c_eth_1.8.1.xdf",
                                 1061)

    print(servo.read('DRV_ID_SOFTWARE_VERSION'))

    net.disconnect_from_slave(servo)


if __name__ == '__main__':
    connection_example()
    sys.exit(0)
