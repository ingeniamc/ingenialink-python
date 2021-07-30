import sys

from ingenialink.canopen.can_net import CanopenNetwork, CAN_DEVICE, CAN_BAUDRATE


def connection_example():
    net = CanopenNetwork(device=CAN_DEVICE.IXXAT,
                         channel=0,
                         baudrate=CAN_BAUDRATE.Baudrate_1M)
    nodes = net.scan_nodes()
    print(nodes)

    if len(nodes) > 0:
        servo = net.connect_to_slave(dictionary='C:/GitProjects/ml3-motionlab3/resources/dictionaries/eve-net-c_can_1.8.1.xdf',
                                     eds='C:/GitProjects/ml3-motionlab3/resources/dictionaries/eds_files/eve-net-c_1.8.1.eds',
                                     node_id=nodes[0])

        fw_version = servo.read('DRV_ID_SOFTWARE_VERSION')
        print(fw_version)

        net.disconnect()
    else:
        print('Could not find any nodes')


if __name__ == '__main__':
    connection_example()
    sys.exit()
