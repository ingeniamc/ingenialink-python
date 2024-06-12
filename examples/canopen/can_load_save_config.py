import argparse

from ingenialink.canopen.network import CAN_BAUDRATE, CAN_DEVICE, CanopenNetwork


def connect_slave(args):
    can_device = CAN_DEVICE(args.transceiver)
    can_baudrate = CAN_BAUDRATE(args.baudrate)
    net = CanopenNetwork(device=can_device, channel=args.channel, baudrate=can_baudrate)

    servo = net.connect_to_slave(target=args.node_id, dictionary=args.dictionary_path)

    return servo, net


def load_config_example(args):
    """Loads a given configuration file into the drive."""
    servo, net = connect_slave(args)
    servo.load_configuration("can_config.xcf")
    servo.load_configuration("can_config_0.xcf", subnode=0)
    servo.load_configuration("can_config_1.xcf", subnode=1)

    net.disconnect_from_slave(servo)


def save_config_example(args):
    """Saves the drive configuration into a file."""

    servo, net = connect_slave(args)
    servo.save_configuration("can_config.xcf")
    servo.save_configuration("can_config_0.xcf", subnode=0)
    servo.save_configuration("can_config_1.xcf", subnode=1)

    net.disconnect_from_slave(servo)


def setup_command():
    parser = argparse.ArgumentParser(description="Canopen example")
    parser.add_argument("-d", "--dictionary_path", help="Path to drive dictionary", required=True)
    parser.add_argument("-n", "--node_id", default=32, type=int, help="Node ID")
    parser.add_argument(
        "-t",
        "--transceiver",
        default="ixxat",
        choices=["pcan", "kvaser", "ixxat"],
        help="CAN transceiver",
    )
    parser.add_argument(
        "-b",
        "--baudrate",
        default=1000000,
        type=int,
        choices=[50000, 100000, 125000, 250000, 500000, 1000000],
        help="CAN baudrate",
    )
    parser.add_argument("-c", "--channel", default=0, type=int, help="CAN transceiver channel")
    return parser.parse_args()


if __name__ == "__main__":
    args = setup_command()
    save_config_example(args)
    load_config_example(args)
