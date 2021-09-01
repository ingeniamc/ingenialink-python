import sys
from time import sleep
import ingenialink as il
from ingenialink.serial.network import SerialNetwork


def serial_scan_drives():
    network = SerialNetwork()
    print(network.scan_slaves())


if __name__ == '__main__':
    serial_scan_drives()
    sys.exit()