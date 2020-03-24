import time
import canopen
from enum import Enum
from threading import Thread
from time import sleep

from .servo_node import Servo
from ..net import NET_PROT, NET_STATE

import logging

log = logging.getLogger(__name__)


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

class CAN_BIT_TIMMING(Enum):
    """ Baudrates. """
    Baudrate_1M = 0
    """ 1 Mbit/s """
    Baudrate_500K = 2
    """ 500 Kbit/s """
    Baudrate_250K = 3
    """ 250 Kbit/s """
    Baudrate_125K = 4
    """ 150 Kbit/s """
    Baudrate_100K = 5
    """ 100 Kbit/s """
    Baudrate_50K = 6
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
                    self.__parent.reset_network()
            else:
                if self.__state != NET_STATE.CONNECTED:
                    self.__parent.net_state = NET_STATE.CONNECTED
                    self.__state = NET_STATE.CONNECTED
                self.__timestamp = self.__node.nmt.timestamp
            sleep(1.5)

    def activate_stop_flag(self):
        self.__stop = True


class Network(object):
    def __init__(self, device=None, baudrate=CAN_BAUDRATE.Baudrate_1M):
        self.__servos = []
        self.__device = device
        self.__baudrate = baudrate
        self.__network = canopen.Network()
        self.__net_state = NET_STATE.DISCONNECTED
        self.__observers = []
        self.__eds = None
        self.__dict = None
        self.__heartbeat_thread = None
        if device is not None:
            try:
                self.__network.connect(bustype=device.value[0], channel=device.value[1], bitrate=baudrate.value)
            except Exception as e:
                print('Exception trying to connect: ', e)

    def change_node_baudrate(self, target_node, vendor_id, product_code, rev_number, serial_number, new_node=None, new_baudrate=None):
        print('\nSwitching slave into CONFIGURATION state...\n')

        bool_result = False
        try:
            bool_result = self.__network.lss.send_switch_state_selective(
                vendor_id,
                product_code,
                rev_number,
                serial_number,
            )
        except Exception as e:
            print('Exception: LSS Timeout. ', e)

        if bool_result:
            if new_baudrate:
                self.__network.lss.configure_bit_timing(CAN_BIT_TIMMING[new_baudrate].value)
                sleep(0.1)
            if new_node:
                self.__network.lss.configure_node_id(new_node)
                sleep(0.1)
            self.__network.lss.store_configuration()
            sleep(0.1)
            print('Stored new configuration')
            self.__network.lss.send_switch_state_global(self.__network.lss.WAITING_STATE)
        else:
            return False

        print('')
        print('Reseting node. Baudrate will be applied after power cycle')
        print('Set properly the baudrate of all the nodes before power cycling the devices')
        self.__network.nodes[target_node].nmt.send_command(0x82)

        # Wait until node is reset
        sleep(0.5)

        self.__network.scanner.reset()
        self.__network.scanner.search()
        sleep(0.5)

        for node_id in self.__network.scanner.nodes:
            print('>> Node found: ', node_id)
            node = self.__network.add_node(node_id, self.__eds)

        # Reset all nodes to default state
        self.__network.lss.send_switch_state_global(self.__network.lss.WAITING_STATE)

        self.__network.nodes[target_node].nmt.start_node_guarding(1)
        return True

    def reset_network(self):
        try:
            self.__network.disconnect()
        except BaseException as e:
            print("Could not reset: Disconnection", e)

        try:
            for node in self.__network.scanner.nodes:
                self.__network.nodes[node].nmt.stop_node_guarding()
            if self.__network.bus:
                self.__network.bus.flush_tx_buffer()
                print("Bus flushed")
        except Exception as e:
            print("Could not stop guarding: ", e)

        try:
            self.__network.connect(bustype=self.__device.value[0], channel=self.__device.value[1], bitrate=self.__baudrate.value)
            for node_id in self.__network.scanner.nodes:
                node = self.__network.add_node(node_id, self.__eds)
                node.nmt.start_node_guarding(1)
        except BaseException as e:
            log.warning(e)
            print("Could not reset: Connection", e)

    def scan(self, eds, dict, boot_mode=False):
        try:
            self.__network.scanner.reset()
            self.__network.scanner.search()
            time.sleep(0.05)
            for node_id in self.__network.scanner.nodes:
                print("Found node %d!" % node_id)
                node = self.__network.add_node(node_id, eds)

                node.nmt.start_node_guarding(1)

                self.__eds = eds
                self.__dict = dict

                if not boot_mode:
                    self.__heartbeat_thread = HearbeatThread(self, node)
                    self.__heartbeat_thread.start()

                self.__servos.append(Servo(self, node, dict, boot_mode=boot_mode))
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
        try:
            for node_id, node_obj in self.__network.nodes.items():
                node_obj.nmt.stop_node_guarding()
        except Exception as e:
            print('Could not stop node guarding. ', e)
        if self.__heartbeat_thread is not None and self.__heartbeat_thread.is_alive():
            self.__heartbeat_thread.activate_stop_flag()
            self.__heartbeat_thread.join()
            self.__heartbeat_thread = None

    def disconnect(self):
        try:
            self.stop_heartbeat()
        except Exception as e:
            print('Disconnect: Exception stop_heartbeat(). {}'.format(e))
        try:
            self.__network.disconnect()
        except Exception as e:
            print('Disconnect: Exception network.disconnect(). {}'.format(e))

    @property
    def servos(self):
        return self.__servos

    @servos.setter
    def servos(self, value):
        self.__servos = value

    @property
    def baudrate(self):
        return self.__baudrate

    @property
    def network(self):
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
