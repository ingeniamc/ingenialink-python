import argparse

from ingenialink.ethernet.network import EthernetNetwork


def connection_example(args: argparse.Namespace) -> None:
    net = EthernetNetwork()
    servo = net.connect_to_slave(args.ip_address, args.dictionary_path, args.port)

    print(servo.read("DRV_ID_SOFTWARE_VERSION"))

    net.disconnect_from_slave(servo)


def setup_command() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ethernet connection example")
    parser.add_argument("-d", "--dictionary_path", help="Path to drive dictionary", required=True)
    parser.add_argument("-ip", "--ip_address", help="IP address", type=str, required=True)
    parser.add_argument("-p", "--port", help="TCP port", type=int, default=1061)
    return parser.parse_args()


if __name__ == "__main__":
    args = setup_command()
    connection_example(args)
