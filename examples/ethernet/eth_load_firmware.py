import argparse

from ingenialink.ethernet.network import EthernetNetwork


def eth_load_fw(args: argparse.Namespace) -> None:
    net = EthernetNetwork()
    net.load_firmware(
        fw_file=args.firmware_path, target=args.ip_address, ftp_user="Ingenia", ftp_pwd="Ingenia"
    )


def setup_command() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ethernet load firmware example")
    parser.add_argument("-f", "--firmware_path", help="Path to firmware file", required=True)
    parser.add_argument("-ip", "--ip_address", help="IP address", type=str, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = setup_command()
    eth_load_fw(args)
