import sys

from ingenialink.canopen.can_net import CanopenNetwork, CAN_DEVICE, CAN_BAUDRATE


def load_config_example():
    net = CanopenNetwork(device=CAN_DEVICE.IXXAT,
                         channel=0,
                         baudrate=CAN_BAUDRATE.Baudrate_1M)

    servo = net.connect_to_slave(target=32,
                                 dictionary='eve-net-c_can_1.8.1.xdf',
                                 eds='eve-net-c_1.8.1.eds')
    servo.load_configuration('can_config.xcf', subnode=0)

    net.disconnect_from_slave(servo)


def save_config_example():
    net = CanopenNetwork(device=CAN_DEVICE.IXXAT,
                         channel=0,
                         baudrate=CAN_BAUDRATE.Baudrate_1M)

    servo = net.connect_to_slave(target=32,
                                 dictionary='eve-net-c_can_1.8.1.xdf',
                                 eds='eve-net-c_1.8.1.eds')
    servo.save_configuration('can_config.xcf', subnode=0)

    net.disconnect_from_slave(servo)


if __name__ == '__main__':
    save_config_example()
    load_config_example()
    sys.exit()
