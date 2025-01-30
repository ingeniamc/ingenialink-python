import argparse

from ingenialink.canopen.network import CanBaudrate, CanDevice, CanopenNetwork


def print_status_message(msg: str) -> None:
    """Example of a callback function."""
    print(f"Current status message: {msg}")


def print_progress(value: int) -> None:
    """Example of a callback function."""
    print(f"Progress: {value}")


def print_progress_total(value: str) -> None:
    """Example of a callback function."""
    print(f"Total progress to be done: {value}")


def print_errors_enabled(value: int) -> None:
    """Example of a callback function."""
    print(f"Errors enabled: {value}")


def load_firmware_example(args: argparse.Namespace) -> None:
    """Loads a firmware to an already connected drive."""
    can_device = CanDevice(args.transceiver)
    can_baudrate = CanBaudrate(args.baudrate)
    net = CanopenNetwork(device=can_device, channel=args.channel, baudrate=can_baudrate)

    nodes = net.scan_slaves()
    print(nodes)

    if len(nodes) > 0:
        servo = net.connect_to_slave(target=args.node_id, dictionary=args.dictionary_path)

        fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
        print("Firmware version before loading new firmware", fw_version)

        net.load_firmware(
            args.node_id,
            args.firmware_path,
            print_status_message,
            print_progress,
            print_errors_enabled,
        )

        fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
        print("Firmware version after loading new firmware", fw_version)

        net.disconnect_from_slave(servo)
    else:
        print("Could not find any nodes")


def load_firmware_example_disconnected() -> None:
    """Loads a firmware to a disconnected drive."""
    net = CanopenNetwork(device=CanDevice.IXXAT, channel=0, baudrate=CanBaudrate.Baudrate_1M)
    net.load_firmware(
        32,
        "../../resources/firmware/eve-net-c_1.8.1.sfu",
        print_status_message,
        print_progress,
        print_errors_enabled,
    )


def setup_command() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Canopen example")
    parser.add_argument("-d", "--dictionary_path", help="Path to drive dictionary", required=True)
    parser.add_argument("-f", "--firmware_path", help="Path to the firmware file", required=True)
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
    load_firmware_example(args)
