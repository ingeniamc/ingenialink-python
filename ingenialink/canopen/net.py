import canopen
from enum import Enum
import time

from .servo_node import Servo


class CAN_DEVICE(Enum):
    """ CAN Device. """
    KVASER  =   ('kvaser', 0)
    """ Kvaser. """
    PCAN    =   ('pcan', 'PCAN_USBBUS1')
    """ Peak. """
    IXXAT   =   ('ixxat', 0)
    """ Ixxat. """

class Network(object):
    def __init__(self, device=None):
        self.__servos = []
        self.__device = device
        self.__network = canopen.Network()
        self.__network.connect(bustype='pcan', channel='PCAN_USBBUS1', bitrate=1000000)

    def scan(self, eds, dict):
        self.__network.scanner.search()
        time.sleep(0.05)
        for node_id in self.__network.scanner.nodes:
            print("Found node %d!" % node_id)
            node = self.__network.add_node(node_id, eds)
            self.__servos.append(Servo(self, node, dict))

    def disconnect(self):
        try:
            self.__network.bus.shutdown()
            self.__network.disconnect()
        except Exception as e:
            print(e)

    @property
    def servos(self):
        return self.__servos

    @servos.setter
    def servos(self, value):
        self.__servos = value

    @property
    def _network(self):
        return self.__network



