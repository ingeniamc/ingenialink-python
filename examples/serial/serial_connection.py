import sys
from time import sleep
import ingenialink as il
from ingenialink.serial.network import SerialNetwork


def connection_example():
    network = SerialNetwork()
    target = "COM5"
    servo = network.connect_to_slave(target,
                                 "../../resources/dictionaries/"
                                 "eve-core_1.8.1.xdf")
    if servo:
        print("Drive Connected in", target)
        print("Status word: ", servo.read("DRV_STATE_STATUS", subnode=1))

    network.disconnect_from_slave(servo)


if __name__ == '__main__':
    connection_example()
    sys.exit()