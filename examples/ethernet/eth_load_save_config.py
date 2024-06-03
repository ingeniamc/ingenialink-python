import sys

from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.ethernet.servo import EthernetServo


def connect_slave() -> tuple[EthernetServo, EthernetNetwork]:
    net = EthernetNetwork()
    servo = net.connect_to_slave("192.168.2.22",
                                 "../../resources/dictionaries/eve-net-c_eth_1.8.1.xdf",
                                 1061)
    return servo, net


def load_config_example() -> None:
    """Loads a given configuration file into the drive."""
    servo, net = connect_slave()
    servo.load_configuration(
        'eth_config.xcf')
    servo.load_configuration(
        'eth_config_0.xcf',
        subnode=0)
    servo.load_configuration(
        'eth_config_1.xcf',
        subnode=1)

    net.disconnect_from_slave(servo)


def save_config_example() -> None:
    """Saves the drive configuration into a file."""
    servo, net = connect_slave()
    servo.save_configuration(
        'eth_config.xcf')
    servo.save_configuration(
        'eth_config_0.xcf',
        subnode=0)
    servo.save_configuration(
        'eth_config_1.xcf',
        subnode=1)

    net.disconnect_from_slave(servo)


if __name__ == '__main__':
    save_config_example()
    load_config_example()
    sys.exit()
