import sys

from ingenialink.canopen.can_net import CanopenNetwork, CAN_DEVICE, CAN_BAUDRATE


def store_restore_example():
    """ Connects to the first scanned drive and store and restores the
    current configuration. """
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

        # Store all
        r = servo.store_parameters(subnode=0)
        if r < 0:
            print('Error storing all parameters')
        else:
            print('Stored all parameters successfully')

        # Store axis 1
        r = servo.store_parameters(subnode=1)
        if r < 0:
            print('Error storing parameters axis 1')
        else:
            print('Stored axis 1 parameters successfully')

        # Restore all
        r = servo.restore_parameters()
        if r < 0:
            print('Error restoring all parameters')
        else:
            print('Restored all parameters successfully')

        net.disconnect_from_slave(servo)
    else:
        print('Could not find any nodes')


if __name__ == '__main__':
    store_restore_example()
    sys.exit()
