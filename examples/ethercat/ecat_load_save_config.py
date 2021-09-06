import sys

from ingenialink.ethercat.network import EthercatNetwork


def connect_slave():
    net = EthercatNetwork("\\Device\\NPF_{192D1D2F-C684-467D-A637-EC07BD434A63}")
    servo = net.connect_to_slave(
        target=1,
        dictionary='../../resources/dictionaries/mancos_1.7.3.xdf')
    return servo, net


def load_config_example():
    """Loads a given configuration file into the drive."""
    servo, net = connect_slave()
    servo.load_configuration('ecat_config.xcf')
    servo.load_configuration('ecat_config_0.xcf', subnode=0)
    servo.load_configuration('ecat_config_1.xcf', subnode=1)

    net.disconnect_from_slave(servo)


def save_config_example():
    """Saves the drive configuration into a file."""
    servo, net = connect_slave()
    servo.save_configuration('ecat_config.xcf')
    servo.save_configuration('ecat_config_0.xcf', subnode=0)
    servo.save_configuration('ecat_config_1.xcf', subnode=1)

    net.disconnect_from_slave(servo)


if __name__ == '__main__':
    save_config_example()
    load_config_example()
    sys.exit()
