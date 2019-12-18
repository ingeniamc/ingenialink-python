import time
import canopen
from enum import Enum
from threading import Thread
from time import sleep

from .servo_node import Servo
from ..net import NET_PROT, NET_STATE

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


class HearbeatThread(Thread):
    def __init__(self, parent, node):
        """ Constructor, setting initial variables """
        super(HearbeatThread, self).__init__()
        self.__parent = parent
        self.__node = node
        self.__timestamp = self.__node.nmt.timestamp
        self.__state = NET_STATE.CONNECTED
        self.__stop = False

    def run(self):
        while not self.__stop:
            if self.__timestamp == self.__node.nmt.timestamp:
                if self.__state != NET_STATE.DISCONNECTED:
                    self.__parent.net_state = NET_STATE.DISCONNECTED
                    self.__state = NET_STATE.DISCONNECTED
            else:
                if self.__state != NET_STATE.CONNECTED:
                    self.__parent.net_state = NET_STATE.CONNECTED
                    self.__state = NET_STATE.CONNECTED
                self.__timestamp = self.__node.nmt.timestamp
            sleep(1)

    def activate_stop_flag(self):
        self.__stop = True


class Network(object):
    def __init__(self, device=None, baudrate=CAN_BAUDRATE.Baudrate_1M):
        self.__servos = []
        self.__device = device
        self.__network = canopen.Network()
        self.__net_state = NET_STATE.DISCONNECTED
        self.__observers = []
        self.__heartbeat_thread = None
        if device is not None:
            try:
                self.__network.connect(bustype=device.value[0], channel=device.value[1], bitrate=baudrate.value)
            except Exception as e:
                print('Exception trying to connect: ', e)

    def scan(self, eds, dict):
        try:
            self.__network.scanner.search()
            time.sleep(0.05)
            for node_id in self.__network.scanner.nodes:
                print("Found node %d!" % node_id)
                node = self.__network.add_node(node_id, eds)

                node.nmt.start_node_guarding(1)

                self.__heartbeat_thread = HearbeatThread(self, node)
                self.__heartbeat_thread.start()

                self.__servos.append(Servo(self, node, dict))
        except Exception as e:
            print('Exception trying to scan: ', e)

    def net_state_subscribe(self, cb):
        """ Subscribe to netowrk state changes.

            Args:
                cb: Callback

            Returns:
                int: Assigned slot.
        """
        r = len(self.__observers)
        self.__observers.append(cb)
        return r

    def stop_heartbeat(self):
        for node_id, node_obj in self.__network.nodes.items():
            node_obj.nmt.stop_node_guarding()
            if self.__heartbeat_thread is not None and self.__heartbeat_thread.is_alive():
                self.__heartbeat_thread.activate_stop_flag()
                self.__heartbeat_thread.join()
                self.__heartbeat_thread = None

    def disconnect(self):
        try:
            self.stop_heartbeat()
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

    @property
    def net_state(self):
        """ Network state. """
        return self.__net_state

    @net_state.setter
    def net_state(self, new_state):
        self.__net_state = new_state
        for callback in self.__observers:
            callback(self.__net_state)
