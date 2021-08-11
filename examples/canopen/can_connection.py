import sys

from ingenialink.canopen.network import CanopenNetwork, CAN_DEVICE, CAN_BAUDRATE


def connection_example():
    """ Scans for nodes in a network, connects to the first found node, reads
    a register and disconnects the found servo from the network. """
    net = CanopenNetwork(device=CAN_DEVICE.IXXAT,
                         channel=0,
                         baudrate=CAN_BAUDRATE.Baudrate_1M)
    nodes = net.scan_slaves()
    print(nodes)

    if len(nodes) > 0:
        servo = net.connect_to_slave(target=nodes[0],
                                     dictionary='eve-net-c_can_1.8.1.xdf',
                                     eds='eve-net-c_1.8.1.eds')

        fw_version = servo.read('DRV_ID_SOFTWARE_VERSION')
        print(fw_version)

        net.disconnect_from_slave(servo)
    else:
        print('Could not find any nodes')


if __name__ == '__main__':
    connection_example()
    sys.exit()
