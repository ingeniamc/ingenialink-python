import argparse

from ingenialink.canopen.network import CAN_BAUDRATE, CAN_DEVICE, CanopenNetwork


def store_restore_example(args):
    """Connects to the first scanned drive and store and restores the
    current configuration."""
    can_device = CAN_DEVICE(args.transceiver)
    can_baudrate = CAN_BAUDRATE(args.baudrate)
    net = CanopenNetwork(device=can_device, channel=args.channel, baudrate=can_baudrate)
    nodes = net.scan_slaves()
    print(nodes)

    if len(nodes) > 0:
        servo = net.connect_to_slave(target=args.node_id, dictionary=args.dictionary_path)

        fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
        print(fw_version)

        # Store all
        try:
            servo.store_parameters()
            print("Stored all parameters successfully")
        except Exception as e:
            print("Error storing all parameters")

        # Store axis 1
        try:
            servo.store_parameters(subnode=1)
            print("Stored axis 1 parameters successfully")
        except Exception as e:
            print("Error storing parameters axis 1")

        # Restore all
        try:
            servo.restore_parameters()
            print("Restored all parameters successfully")
        except Exception as e:
            print("Error restoring all parameters")

        net.disconnect_from_slave(servo)
    else:
        print("Could not find any nodes")


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
    store_restore_example(args)
