import sys

from ingenialink.ethernet.network import EthernetNetwork, NET_TRANS_PROT


def connect_slave():
    net = EthernetNetwork()
    servo = net.connect_to_slave("192.168.2.22",
                                 "../../resources/dictionaries/eve-net-c_eth_1.8.1.xdf",
                                 1061,
                                 NET_TRANS_PROT.UDP)
    return servo, net


def load_config_example():
    """ Loads a given configuration file into the drive."""
    servo, net = connect_slave()
    servo.load_configuration('../../resources/configurations/eth_config.xcf', subnode=0)

    net.disconnect_from_slave(servo)


def save_config_example():
    """ Saves the drive configuration into a file."""
    servo, net = connect_slave()
    servo.save_configuration('../../resources/configurations/eth_config.xcf', subnode=0)

    net.disconnect_from_slave(servo)


if __name__ == '__main__':
    save_config_example()
    load_config_example()
    sys.exit()
