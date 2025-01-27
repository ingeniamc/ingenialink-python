import argparse

from ingenialink.canopen.network import CanBaudrate, CanDevice, CanopenNetwork


def connection_example(args: argparse.Namespace) -> None:
    """Scans for nodes in a network, connects to the first found node, reads
    a register and disconnects the found servo from the network.

    Args:
        dict_path: Path to the dictionary
    """
    can_baudrate = CanBaudrate(args.baudrate)
    net = CanopenNetwork(device=CanDevice.SOCKETCAN, channel=args.channel, baudrate=can_baudrate)
    nodes = net.scan_slaves()
    print(nodes)

    if len(nodes) > 0:
        servo = net.connect_to_slave(target=args.node_id, dictionary=args.dictionary_path)

        fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
        print(fw_version)

        net.disconnect_from_slave(servo)
    else:
        print("Could not find any nodes")


def setup_command() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Canopen example")
    parser.add_argument("-d", "--dictionary_path", help="Path to drive dictionary", required=True)
    parser.add_argument("-n", "--node_id", default=32, type=int, help="Node ID")
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
    connection_example(args)
