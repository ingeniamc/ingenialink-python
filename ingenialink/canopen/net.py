import time
import canopen
from enum import Enum

from .servo_node import Servo
from ..net import NET_PROT

class CAN_DEVICE(Enum):
    """ CAN Device. """
    KVASER  =   ('kvaser', 0)
    """ Kvaser. """
    PCAN    =   ('pcan', 'PCAN_USBBUS1')
    """ Peak. """
    IXXAT   =   ('ixxat', 0)
    """ Ixxat. """


class CAN_BAUDRATE(Enum):
    """ Baudrates. """
    Baudrate_1M = 1000000
    """ 1 Mbit/s """
    Baudrate_500K = 500000
    """ 500 Kbit/s """
    Baudrate_250K = 250000
    """ 250 Kbit/s """
    Baudrate_125K = 125000
    """ 150 Kbit/s """
    Baudrate_100K = 100000
    """ 100 Kbit/s """
    Baudrate_50K = 50000
    """ 50 Kbit/s """


class Network(object):
    def __init__(self, device=None, baudrate=CAN_BAUDRATE.Baudrate_1M):
        self.__servos = []
        self.__device = device
        self.__network = canopen.Network()
        if device is not None:
            self.__network.connect(bustype=device.value[0], channel=device.value[1], bitrate=baudrate.value)

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

    @property
    def prot(self):
        """ NET_PROT: Obtain network protocol. """
        return NET_PROT.CAN
