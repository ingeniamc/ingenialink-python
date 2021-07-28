import sys

import ingenialink as il
from ingenialink.ethernet.eth_net import EthernetNetwork
from ingenialink.net import Network


def eth_example():
    network = EthernetNetwork("192.168.2.22",
                              "eve-xcr_1.7.1.xdf",
                              1061,
                              il.net.NET_TRANS_PROT.UDP.value)
    r, servo = network.connect()


if __name__ == '__main__':
    eth_example()
    sys.exit(0)