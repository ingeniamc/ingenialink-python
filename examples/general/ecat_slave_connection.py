import sys
from time import time, sleep
import ingenialink as il


def slave_connection():
    # Connection
    servo = None
    net = None
    enum = il.NET_PROT.ECAT

    # SOEM Connection
    try:
        servo, net = il.servo.connect_ecat("\\Device\\NPF_{E8228BC6-D9E5-4CD0-BCDC-A9023F7977B3}",
                                           "192.168.2.1",
                                           "resources/eve-net_1.7.1.xdf",
                                           "192.168.2.22")
        if servo is not None and net is not None:
            # Read a couple of registers
            print('>> SOFTWARE_VERSION:', servo.read('DRV_ID_SOFTWARE_VERSION'))
            print('>> BUS_VOLTAGE:', servo.read('DRV_PROT_VBUS_VALUE'))

            sleep(1)
            # Disconnect the drive
            net.master_stop()
            print("Disconnected!")
        else:
            print('Could not connect to drive')
    except BaseException as e:
        print('Error while connecting to drive. Exception: {}'.format(e))


if __name__ == '__main__':
    slave_connection()
    sys.exit(0)
