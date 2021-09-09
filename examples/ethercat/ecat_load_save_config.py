import sys

from ingenialink.ethercat.network import EthercatNetwork


def connect_slave():
    net = EthercatNetwork("\\Device\\NPF_{192D1D2F-C684-467D-A637-EC07BD434A63}")
    servo = net.connect_to_slave(
        target=1,
        dictionary='../../resources/dictionaries/cap-net-e_eoe_0.7.1.xdf')
    return servo, net


def load_config_example():
    """Loads a given configuration file into the drive."""
    servo, net = connect_slave()
    servo.load_configuration('../../resources/dictionaries/ethercat-config.xdf')

    net.disconnect_from_slave(servo)


def save_config_example():
    """Saves the drive configuration into a file."""
    servo, net = connect_slave()
    servo.save_configuration('../../resources/dictionaries/ethercat-config.xdf')

    net.disconnect_from_slave(servo)


if __name__ == '__main__':
    save_config_example()
    load_config_example()
    sys.exit()
