import argparse

from ingenialink.ethercat.network import EthercatNetwork


def main(args: argparse.Namespace) -> None:
    net = EthercatNetwork(args.interface)
    servo = net.connect_to_slave(args.slave_id, args.dictionary_path)
    firmware_version = servo.read("DRV_ID_SOFTWARE_VERSION")
    print(firmware_version)
    net.disconnect_from_slave(servo)


def setup_command() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EtherCAT connection example script.")
    interface_help = """Network adapter interface name. To find it: \n
    - On Windows, \\Device\\NPF_{id}. To get the id, run the command: wmic nic get name, guid \n
    - On linux, run the command: ip link show
    """
    parser.add_argument("-i", "--interface", type=str, help=interface_help, required=True)
    parser.add_argument(
        "-d", "--dictionary_path", type=str, help="Path to the drive's dictionary.", required=True
    )
    parser.add_argument("-s", "--slave_id", type=int, help="Slave ID.", default=1)
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = setup_command()
    main(args)
