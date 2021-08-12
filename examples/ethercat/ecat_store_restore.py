import sys

from ingenialink.ethercat.network import EthercatNetwork


def connect_slave():
    net = EthercatNetwork("\\Device\\NPF_{192D1D2F-C684-467D-A637-EC07BD434A63}")
    servo = net.connect_to_slave(
        target=1,
        dictionary='../../resources/dictionaries/cap-net-e_eoe_0.7.1.xdf')
    return servo, net


def store_restore_example():
    """ Connects to the first scanned drive and store and restores the
    current configuration. """

    servo, net = connect_slave()

    # Store all
    try:
        servo.store_parameters(subnode=0)
        print('Stored all parameters successfully')
    except Exception as e:
        print('Error storing all parameters')

    # Store axis 1
    try:
        servo.store_parameters(subnode=1)
        print('Stored axis 1 parameters successfully')
    except Exception as e:
        print('Error storing parameters axis 1')

    # Restore all
    try:
        servo.restore_parameters()
        print('Restored all parameters successfully')
    except Exception as e:
        print('Error restoring all parameters')

    net.disconnect_from_slave(servo)


if __name__ == '__main__':
    store_restore_example()
    sys.exit()
