import argparse

from ingenialink.ethercat.network import EthercatNetwork


def ecat_load_fw(args):
    net = EthercatNetwork(args.interface)
    boot_in_app = args.firmware_path.endswith(".sfu")
    net.load_firmware(args.firmware_path, boot_in_app, slave_id=args.slave_id)


def setup_command():
    parser = argparse.ArgumentParser(description="EtherCAT connection example script.")
    interface_help = """Network adapter interface name. To find it: \n
    - On Windows, \\Device\\NPF_{id}. To get the id, run the command: wmic nic get name, guid \n
    - On linux, run the command: ip link show
    """
    parser.add_argument("-i", "--interface", type=str, help=interface_help, required=True)
    parser.add_argument(
        "-f", "--firmware_path", type=str, help="Path to the firmware file.", required=True
    )
    parser.add_argument("-s", "--slave_id", type=int, help="Slave ID.", default=1)
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = setup_command()
    ecat_load_fw(args)
