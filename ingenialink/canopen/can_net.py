import time
import canopen
from enum import Enum
from threading import Thread
from time import sleep
from can.interfaces.pcan.pcan import PcanError
from can.interfaces.ixxat.exceptions import VCIDeviceNotFoundError

from .._utils import *
from .._ingenialink import lib
from .can_servo import CanopenServo
from ..net import NET_PROT, NET_STATE, Network

import ingenialogger

logger = ingenialogger.get_logger(__name__)

CAN_CHANNELS = {
    'kvaser': (0, 1),
    'pcan': ('PCAN_USBBUS1', 'PCAN_USBBUS2'),
    'ixxat': (0, 1)
}


class CAN_DEVICE(Enum):
    """ CAN Device. """
    KVASER = 'kvaser'
    """ Kvaser. """
    PCAN = 'pcan'
    """ Peak. """
    IXXAT = 'ixxat'
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
    """ 125 Kbit/s """
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


class NetStatusListener(Thread):
    """ Network status listener thread to check if the drive is alive.

    Args:
        parent (Network): network instance of the CANopen communication.
        node (int): Identifier for the targeted node ID.
    """

    def __init__(self, parent, node):
        super(NetStatusListener, self).__init__()
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


class CanopenNetwork(Network):
    """ Network of the CANopen communication.

    Args:
        device (CAN_DEVICE): Targeted device to connect.
        channel (int): Targeted channel number of the transceiver.
        baudrate (CAN_BAUDRATE): Baudrate to communicate through.
    """

    def __init__(self, device=None, channel=0, baudrate=CAN_BAUDRATE.Baudrate_1M):
        self.__servos = []
        self.__device = device.value
        self.__channel = CAN_CHANNELS[self.__device][channel]
        self.__baudrate = baudrate.value
        self.__connection = None
        self.__net_state = NET_STATE.DISCONNECTED
        self.__observers = []
        self.__eds = None
        self.__dict = None
        self.__net_status_listener = None

    def change_node_baudrate(self, target_node, vendor_id, product_code,
                             rev_number, serial_number, new_node=None,
                             new_baudrate=None):
        """ Changes the node ID and the baurdrate of a targeted drive.

        Args:
            target_node (int): Node ID of the targeted device.
            vendor_id (int): Vendor ID of the targeted device.
            product_code (int): Product code of the targeted device.
            rev_number (int): Revision number of the targeted device.
            serial_number (int): Serial number of the targeted device.
            new_node (int): New node ID for the targeted device.
            new_baudrate (int): New baudrate for the targeted device.

        Returns:
            bool: Result of the operation.
        """
        logger.debug("Switching slave into CONFIGURATION state...")
        bool_result = False
        try:
            bool_result = self.__connection.lss.send_switch_state_selective(
                vendor_id,
                product_code,
                rev_number,
                serial_number,
            )
        except Exception as e:
            logger.error('LSS Timeout. Exception: %s', e)

        if bool_result:
            if new_baudrate:
                self.__connection.lss.configure_bit_timing(
                    CAN_BIT_TIMMING[new_baudrate].value
                )
                sleep(0.1)
            if new_node:
                self.__connection.lss.configure_node_id(new_node)
                sleep(0.1)
            self.__connection.lss.store_configuration()
            sleep(0.1)
            logger.info('Stored new configuration')
            self.__connection.lss.send_switch_state_global(
                self.__connection.lss.WAITING_STATE
            )
        else:
            return False

        self.__connection.nodes[target_node].nmt.send_command(0x82)

        logger.debug("Wait until node is reset")
        sleep(0.5)

        logger.debug("Searching for nodes...")
        nodes = self.detect_nodes()

        for node_id in nodes:
            logger.info('Node found: %i', node_id)
            node = self.__connection.add_node(node_id, self.__eds)

        # Reset all nodes to default state
        self.__connection.lss.send_switch_state_global(
            self.__connection.lss.WAITING_STATE
        )

        self.__connection.nodes[target_node].nmt.start_node_guarding(1)
        return True

    def reset_network(self):
        """ Resets the established CANopen network. """
        try:
            self.__connection.disconnect()
        except BaseException as e:
            logger.error("Disconnection failed. Exception: %", e)

        try:
            for node in self.__connection.scanner.nodes:
                self.__connection.nodes[node].nmt.stop_node_guarding()
            if self.__connection.bus:
                self.__connection.bus.flush_tx_buffer()
                logger.info("Bus flushed")
        except Exception as e:
            logger.error("Could not stop guarding. Exception: %", e)

        try:
            self.__connection.connect(bustype=self.__device,
                                      channel=self.__channel,
                                      bitrate=self.__baudrate)
            for node_id in self.__connection.scanner.nodes:
                node = self.__connection.add_node(node_id, self.__eds)
                node.nmt.start_node_guarding(1)
        except BaseException as e:
            logger.error("Connection failed. Exception: %s", e)

    @deprecated(new_func_name='scan_nodes')
    def detect_nodes(self):
        """ Scans for nodes in the network.

        Returns:
            list: Containing all the detected node IDs.
        """
        self.__connection.scanner.reset()
        try:
            self.__connection.scanner.search()
        except Exception as e:
            logger.error("Error searching for nodes. Exception: {}".format(e))
            logger.info("Resetting bus")
            self.__connection.bus.reset()
        time.sleep(0.05)
        return self.__connection.scanner.nodes

    def scan_nodes(self):
        """ Scans for nodes in the network.

        Returns:
            list: Containing all the detected node IDs.
        """
        self.setup_connection()

        self.__connection.scanner.reset()
        try:
            self.__connection.scanner.search()
        except Exception as e:
            logger.error("Error searching for nodes. Exception: {}".format(e))
            logger.info("Resetting bus")
            self.__connection.bus.reset()
        time.sleep(0.05)

        nodes = self.__connection.scanner.nodes

        self.teardown_connection()

        return nodes

    def setup_connection(self):
        if self.__device is not None and self.__connection is None:
            self.__connection = canopen.Network()

            try:
                self.__connection.connect(bustype=self.__device,
                                          channel=self.__channel,
                                          bitrate=self.__baudrate)
            except (PcanError, VCIDeviceNotFoundError) as e:
                logger.error('Transceiver not found in network. Exception: %s', e)
                raise_err(lib.IL_EFAIL, 'Error connecting to the transceiver. '
                                        'Please verify the transceiver is properly connected.')
            except OSError as e:
                logger.error('Transceiver drivers not properly installed. Exception: %s', e)
                if hasattr(e, 'winerror') and e.winerror == 126:
                    e.strerror = 'Driver module not found.' \
                                 ' Drivers might not be properly installed.'
                raise_err(lib.IL_EFAIL, e)
            except Exception as e:
                logger.error('Failed trying to connect. Exception: %s', e)
                raise_err(lib.IL_EFAIL, 'Failed trying to connect. {}'.format(e))

    def teardown_connection(self):
        self.__connection.disconnect()
        # TODO: del connection object
        self.__connection = None

    def connect_to_slave(self, target, dictionary, eds, servo_status_listener=False, net_status_listener=True):
        """ Connects to a drive through a given node ID.

        Args:
            eds (str): Path to the EDS file.
            dictionary (str): Path to the dictionary file.
            target (int): Targeted node ID to be connected.
            servo_status_listener (bool): Boolean to initialize the ServoStatusListener and check the drive status.
            net_status_listener (bool): Value to initialize the NetStatusListener.
        """
        nodes = self.scan_nodes()
        if len(nodes) < 1:
            raise_err(lib.IL_EFAIL, 'Could not find any nodes in the network')

        self.setup_connection()
        if target in nodes:
            try:
                node = self.__connection.add_node(target, eds)

                node.nmt.start_node_guarding(1)

                self.__eds = eds
                self.__dict = dictionary

                if net_status_listener:
                    self.__net_status_listener = NetStatusListener(self, node)
                    self.__net_status_listener.start()

                servo = CanopenServo(self, target, node, dictionary,
                                     servo_status_listener=servo_status_listener)
                self.__servos.append(servo)
                return servo
            except Exception as e:
                logger.error("Failed connecting to node %i. Exception: %s",
                             target, e)
                raise_err(lib.IL_EFAIL,
                          'Failed connecting to node {}. Please check the connection settings and verify '
                          'the transceiver is properly connected.'.format(target))
        else:
            logger.error('Node id not found')
            raise_err(lib.IL_EFAIL, 'Node id {} not found in the network.'.format(target))

    @deprecated('connect')
    def connect_through_node(self, eds, dict, node_id, servo_status_listener=False,
                             net_status_listener=True):
        """ Connects to a drive through a given node ID.

        Args:
            eds (str): Path to the EDS file.
            dict (str): Path to the dictionary file.
            node_id (int): Targeted node ID to be connected.
            servo_status_listener (bool): Boolean to initialize the ServoStatusListener and check the drive status.
            net_status_listener (bool): Value to initialize the NetStatusListener.
        """
        nodes = self.detect_nodes()
        if len(nodes) < 1:
            raise_err(lib.IL_EFAIL, 'Could not find any nodes in the network')

        if node_id in nodes:
            try:
                node = self.__connection.add_node(node_id, eds)

                node.nmt.start_node_guarding(1)

                self.__eds = eds
                self.__dict = dict

                if net_status_listener:
                    self.__net_status_listener = NetStatusListener(self, node)
                    self.__net_status_listener.start()

                self.__servos.append(CanopenServo(self, node, dict,
                                                  servo_status_listener=servo_status_listener))
            except Exception as e:
                logger.error("Failed connecting to node %i. Exception: %s",
                             node_id, e)
                raise_err(lib.IL_EFAIL,
                          'Failed connecting to node {}. Please check the connection settings and verify '
                          'the transceiver is properly connected.'.format(node_id))
        else:
            logger.error('Node id not found')
            raise_err(lib.IL_EFAIL, 'Node id {} not found in the network.'.format(node_id))

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

    def stop_net_status_listener(self):
        """ Stops the NetStatusListener from listening to the drive. """
        try:
            for node_id, node_obj in self.__connection.nodes.items():
                node_obj.nmt.stop_node_guarding()
        except Exception as e:
            logger.error('Could not stop node guarding. Exception: %s', e)
        if self.__net_status_listener is not None and \
                self.__net_status_listener.is_alive():
            self.__net_status_listener.activate_stop_flag()
            self.__net_status_listener.join()
            self.__net_status_listener = None

    def disconnect_from_slave(self, servo):
        """ Disconnects the already established network. """
        try:
            self.stop_net_status_listener()
        except Exception as e:
            logger.error('Failed stopping net_status_listener. Exception: %s', e)

        try:
            servo.stop_status_listener()
        except Exception as e:
            logger.error('Failed stopping drive status thread. Exception: %s', e)

        # TODO: Delete servo instance from servos list

        try:
            self.__connection.disconnect()
        except Exception as e:
            logger.error('Failed disconnecting. Exception: %s', e)
            raise_err(lib.IL_EFAIL, 'Failed disconnecting.')

    @property
    def servos(self):
        """ list: Servos available in the network. """
        return self.__servos

    @servos.setter
    def servos(self, value):
        self.__servos = value

    @property
    def baudrate(self):
        """ int: Current baudrate of the network. """
        return self.__baudrate

    @property
    def network(self):
        """ canopen.Network: Returns the instance of the CANopen Network. """
        return self.__connection

    @property
    def prot(self):
        """ NET_PROT: Obtain network protocol. """
        return NET_PROT.CAN

    @property
    def net_state(self):
        """ NET_STATE: Network state."""
        return self.__net_state

    @net_state.setter
    def net_state(self, new_state):
        self.__net_state = new_state
        for callback in self.__observers:
            callback(self.__net_state)
