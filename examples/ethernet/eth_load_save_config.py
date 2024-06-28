import argparse

from ingenialink.ethernet.network import EthernetNetwork
from ingenialink.ethernet.servo import EthernetServo


def connect_slave(args: argparse.Namespace) -> tuple[EthernetServo, EthernetNetwork]:
    net = EthernetNetwork()
    servo = net.connect_to_slave(args.ip_address, args.dictionary_path, args.port)
    return servo, net


def load_config_example(args: argparse.Namespace) -> None:
    """Loads a given configuration file into the drive."""
    servo, net = connect_slave(args)
    servo.load_configuration("eth_config.xcf")
    servo.load_configuration("eth_config_0.xcf", subnode=0)
    servo.load_configuration("eth_config_1.xcf", subnode=1)

    net.disconnect_from_slave(servo)


def save_config_example(args: argparse.Namespace) -> None:
    """Saves the drive configuration into a file."""
    servo, net = connect_slave(args)
    servo.save_configuration("eth_config.xcf")
    servo.save_configuration("eth_config_0.xcf", subnode=0)
    servo.save_configuration("eth_config_1.xcf", subnode=1)

    net.disconnect_from_slave(servo)


def setup_command() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ethernet connection example")
    parser.add_argument("-d", "--dictionary_path", help="Path to drive dictionary", required=True)
    parser.add_argument("-ip", "--ip_address", help="IP address", type=str, required=True)
    parser.add_argument("-p", "--port", help="TCP port", type=int, default=1061)
    return parser.parse_args()


if __name__ == "__main__":
    args = setup_command()
    save_config_example(args)
    load_config_example(args)
