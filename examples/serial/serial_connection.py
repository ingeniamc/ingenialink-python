import sys
from time import sleep
import ingenialink as il
from ingenialink.serial.network import SerialNetwork


def connection_example():
    network = SerialNetwork()
    servo = network.connect_to_slave("COM5",
                                 "../../resources/dictionaries/"
                                 "eve-core_1.8.1.xdf")
    if servo:
        print("connected!")
        print("Status word: ", servo.read("DRV_STATE_STATUS", subnode=1))

    network.disconnect_from_slave(servo)


if __name__ == '__main__':
    connection_example()
    sys.exit()