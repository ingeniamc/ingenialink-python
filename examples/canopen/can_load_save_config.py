import sys

from ingenialink.canopen.network import CAN_BAUDRATE, CAN_DEVICE, CanopenNetwork
from ingenialink.canopen.servo import CanopenServo


def connect_slave() -> tuple[CanopenServo, CanopenNetwork]:
    net = CanopenNetwork(device=CAN_DEVICE.IXXAT, channel=0, baudrate=CAN_BAUDRATE.Baudrate_1M)

    servo = net.connect_to_slave(
        target=32,
        dictionary='../../resources/dictionaries/eve-net-c_can_1.8.1.xdf')
    
    return servo, net


def load_config_example() -> None:
    """Loads a given configuration file into the drive."""
    servo, net = connect_slave()
    servo.load_configuration(
        'can_config.xcf')
    servo.load_configuration(
        'can_config_0.xcf',
        subnode=0)
    servo.load_configuration(
        'can_config_1.xcf',
        subnode=1)

    net.disconnect_from_slave(servo)


def save_config_example() -> None:
    """Saves the drive configuration into a file."""

    servo, net = connect_slave()
    servo.save_configuration(
        'can_config.xcf')
    servo.save_configuration(
        'can_config_0.xcf',
        subnode=0)
    servo.save_configuration(
        'can_config_1.xcf',
        subnode=1)

    net.disconnect_from_slave(servo)


if __name__ == '__main__':
    save_config_example()
    load_config_example()
    sys.exit()
