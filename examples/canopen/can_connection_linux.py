import sys

from ingenialink.canopen.network import CAN_BAUDRATE, CAN_DEVICE, CanopenNetwork


def connection_example(dict_path: str) -> None:
    """Scans for nodes in a network, connects to the first found node, reads
    a register and disconnects the found servo from the network.

    Args:
        dict_path: Path to the dictionary
    """
    net = CanopenNetwork(device=CAN_DEVICE.SOCKETCAN, channel=0, baudrate=CAN_BAUDRATE.Baudrate_1M)
    nodes = net.scan_slaves()
    print(nodes)

    if len(nodes) > 0:
        servo = net.connect_to_slave(target=nodes[0], dictionary=dict_path)

        fw_version = servo.read("DRV_ID_SOFTWARE_VERSION")
        print(fw_version)

        net.disconnect_from_slave(servo)
    else:
        print("Could not find any nodes")


if __name__ == "__main__":
    dict_path = "../../resources/dictionaries/eve-net-c_can_1.8.1.xdf"
    connection_example(dict_path)
    sys.exit()
