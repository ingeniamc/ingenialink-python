import canopen
from enum import Enum
import time


class CAN_DEVICE(Enum):
    """ CAN Device. """
    KVASER  =   ('kvaser', 0)
    """ Kvaser. """
    PCAN    =   ('pcan', 'PCAN_USBBUS1')
    """ Peak. """
    IXXAT   =   ('ixxat', 0)
    """ Ixxat. """
    NICAN   =   ('nican', 'CAN0')
    """ Nican. """

class Network(object):
    def __init__(self, device=None):
        self.__servos = []
        self.__device = device
        self.__network = canopen.Network()
        self.__network.connect(bustype='kvaser', channel=0, bitrate=1000000)

    def scan(self, eds_filepath, dict_filepath):
        self.__network.scanner.search()
        time.sleep(0.05)
        for node_id in self.__network.scanner.nodes:
            print("Found node %d!" % node_id)
            node = self.__network.add_node(node_id, eds_filepath)
            print(node)
            for obj in node.object_dictionary.values():
                print('0x%X: %s' % (obj.index, obj.name))
                if isinstance(obj, canopen.objectdictionary.Record):
                    for subobj in obj.values():
                        print('  %d: %s' % (subobj.subindex, subobj.name))



    def disconnect(self):
        self.__network.disconnect()

    @property
    def servos(self):
        return self.__servos

    @servos.setter
    def servos(self, value):
        self.__servos = value

    @property
    def _network(self):
        return self.__network



