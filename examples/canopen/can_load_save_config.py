import sys

from ingenialink.canopen.network import CanopenNetwork, CAN_DEVICE, CAN_BAUDRATE


def load_config_example():
    """Loads a given configuration file into the drive."""
    net = CanopenNetwork(device=CAN_DEVICE.IXXAT,
                         channel=0,
                         baudrate=CAN_BAUDRATE.Baudrate_1M)

    servo = net.connect_to_slave(
        target=32,
        dictionary='../../resources/dictionaries/eve-net-c_can_1.8.1.xdf',
        eds='../../resources/dictionaries/eve-net-c_1.8.1.eds')
    servo.load_configuration('../../resources/configurations/canopen-config.xcf')

    net.disconnect_from_slave(servo)


def save_config_example():
    """Saves the drive configuration into a file."""
    net = CanopenNetwork(device=CAN_DEVICE.IXXAT,
                         channel=0,
                         baudrate=CAN_BAUDRATE.Baudrate_1M)

    servo = net.connect_to_slave(
        target=32,
        dictionary='../../resources/dictionaries/eve-net-c_can_1.8.1.xdf',
        eds='../../resources/dictionaries/eve-net-c_1.8.1.eds')
    servo.save_configuration('../../resources/configurations/canopen-config.xcf')

    net.disconnect_from_slave(servo)


if __name__ == '__main__':
    save_config_example()
    load_config_example()
    sys.exit()
