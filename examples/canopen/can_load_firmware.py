from ingenialink.canopen.network import CanopenNetwork, CAN_DEVICE, CAN_BAUDRATE

import sys


def print_status_message(msg):
    """ Example of a callback function. """
    print('Current status message: {}'.format(msg))


def print_progress(value):
    """ Example of a callback function. """
    print('Progress: {}'.format(value))


def print_progress_total(value):
    """ Example of a callback function. """
    print('Total progress to be done: {}'.format(value))


def print_errors_enabled(value):
    """ Example of a callback function. """
    print('Errors enabled: {}'.format(value))


def load_firmware_example_connected():
    """ Loads a firmware to an already connected drive. """
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
        print('Firmware version before loading new firmware', fw_version)

        net.subscribe_to_load_firmware_process(
            callback_status_msg=print_status_message,
            callback_progress=print_progress,
            callback_errors_enabled=print_errors_enabled)
        net.load_firmware(nodes[0], 'eve-net-c_1.8.1.sfu')

        fw_version = servo.read('DRV_ID_SOFTWARE_VERSION')
        print('Firmware version after loading new firmware', fw_version)

        net.disconnect_from_slave(servo)
    else:
        print('Could not find any nodes')


def load_firmware_example_disconnected():
    """ Loads a firmware to a disconnected drive. """
    net = CanopenNetwork(device=CAN_DEVICE.IXXAT,
                         channel=0,
                         baudrate=CAN_BAUDRATE.Baudrate_1M)

    net.subscribe_to_load_firmware_process(
        callback_status_msg=print_status_message,
        callback_progress=print_progress,
        callback_errors_enabled=print_errors_enabled)
    net.load_firmware(32, '../../resources/firmware/eve-net-c_1.8.1.sfu')


if __name__ == '__main__':
    load_firmware_example_connected()
    load_firmware_example_disconnected()
    sys.exit()
