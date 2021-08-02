from enum import Enum
from time import sleep, time
from threading import Thread
from .._ingenialink import lib
from .can_register import Register
from ingenialink.utils.mcb import MCB
from ingenialink.utils._utils import *
from ..exceptions import ILFirmwareLoadError
from can.interfaces.pcan.pcan import PcanError
from ..net import NET_PROT, NET_STATE, Network
from can.interfaces.ixxat.exceptions import VCIDeviceNotFoundError
from .can_servo import CanopenServo, REG_ACCESS, REG_DTYPE, CANOPEN_SDO_RESPONSE_TIMEOUT

import re
import os
import canopen
import tempfile
import ingenialogger

logger = ingenialogger.get_logger(__name__)

PROG_STAT_1 = Register(
    identifier='', units='', subnode=0, idx="0x1F51", subidx="0x01", cyclic='CONFIG',
    dtype=REG_DTYPE.U8, access=REG_ACCESS.RW
)
PROG_DL_1 = Register(
    identifier='', units='', subnode=0, idx="0x1F50", subidx="0x01", cyclic='CONFIG',
    dtype=REG_DTYPE.DOMAIN, access=REG_ACCESS.RW
)
FORCE_BOOT = Register(
    identifier='', units='', subnode=0, idx="0x5EDE", subidx="0x00", cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.WO
)

CIA301_DRV_ID_DEVICE_TYPE = Register(
    identifier='', units='', subnode=0, idx="0x1000", subidx="0x00", cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
)

BOOTLOADER_MSG_SIZE = 256           # Size in Bytes
RECONNECTION_TIMEOUT = 180          # Seconds
POLLING_MAX_TRIES = 5               # Seconds

PROG_CTRL_STATE_STOP = 0x00
PROG_CTRL_STATE_START = 0x01
PROG_CTRL_STATE_CLEAR = 0x03
PROG_CTRL_STATE_FLASH = 0x80

APPLICATION_LOADED_STATE = 402

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
                    self.__parent.reset_connection()
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

    def __init__(self, device, channel=0, baudrate=CAN_BAUDRATE.Baudrate_1M):
        super(CanopenNetwork, self).__init__()
        self.__device = device.value
        self.__channel = CAN_CHANNELS[self.__device][channel]
        self.__baudrate = baudrate.value
        self.__connection = None
        self.__net_state = NET_STATE.DISCONNECTED
        self.__observers_net_state = []
        self.__eds = None
        self.__dict = None
        self.__net_status_listener = None

        # Firmware loader observers
        self.__fw_load_observers = []
        self.__observers_fw_load_status_msg = []
        self.__observers_fw_load_progress = []
        self.__observers_fw_load_progress_total = []
        self.__observers_fw_load_errors_enabled = []

        self.__fw_load_status_msg = ''
        self.__fw_load_progress = 0
        self.__fw_load_progress_total = 100
        self.__fw_load_errors_enabled = True

    def scan_slaves(self):
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
        sleep(0.05)

        nodes = self.__connection.scanner.nodes

        self.teardown_connection()

        return nodes
    
    def connect_to_slave(self, target, dictionary=None, eds=None,
                         servo_status_listener=False, net_status_listener=True):
        """ Connects to a drive through a given target node ID.

        Args:
            target (int): Targeted node ID to be connected.
            dictionary (str): Path to the dictionary file.
            eds (str): Path to the EDS file.
            servo_status_listener (bool): Toggle the listener of the servo for its status (errors, faults, etc).
            net_status_listener (bool): Toggle the listener of the network status (connection and disconnection)
        """
        nodes = self.scan_slaves()
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
                self.servos.append(servo)
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

        self.servos.remove(servo)

        try:
            self.__connection.disconnect()
        except Exception as e:
            logger.error('Failed disconnecting. Exception: %s', e)
            raise_err(lib.IL_EFAIL, 'Failed disconnecting.')

    def setup_connection(self):
        """ Establishes an empty connection with all the network attributes
        already specified. """
        if self.__connection is None:
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
        else:
            logger.info('Connection already established')
    
    def teardown_connection(self):
        """ Tears down the already established connection. """
        self.__connection.disconnect()
        del self.__connection
        self.__connection = None
        logger.info('Tear down connection.')

    def reset_connection(self):
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

    def subscribe_to_load_firmware_process(self, callback_status_msg=None, callback_progress=None,
                                           callback_progress_total=None, callback_errors_enabled=None):
        """ Subscribe all the callback methods to its specific variable observer.

        Args:
            callback_status_msg (object): Subscribed callback function for the status
            message when loading a firmware.
            callback_progress (object): Subscribed callback function for the live
            progress when loading a firmware.
            callback_progress_total (object): Subscribed callback function for the total
            progress when loading a firmware.
            callback_errors_enabled (object): Subscribed callback function for knowing when to
            toggle the error detection when loading firmware.

        """
        if callback_status_msg is not None:
            self.__observers_fw_load_status_msg.append(callback_status_msg)
        if callback_progress is not None:
            self.__observers_fw_load_progress.append(callback_progress)
        if callback_progress_total is not None:
            self.__observers_fw_load_progress_total.append(callback_progress_total)
        if callback_errors_enabled is not None:
            self.__observers_fw_load_errors_enabled.append(callback_errors_enabled)

    def load_firmware(self, target, fw_file):
        """ Loads a given firmware file to a target.

        Args:
            target (int): Targeted node ID to be loaded.
            fw_file (str): Path to the firmware file.

        Raises:
            ILFirmwareLoadError: The firmware load process fails with an error message.

        """
        self.set_fw_load_status_msg('')
        self.set_fw_load_progress(0)
        self.set_fw_load_progress_total(100)
        self.set_fw_load_errors_enabled(True)

        servo = None
        lfu_path = None
        error_detected_msg = ''
        servo_connected = False
        error_connecting = False

        # Check if target is already connected
        for servo in self.servos:
            if servo.target == target:
                servo_connected = True
                break
            else:
                servo = None

        try:
            if not servo_connected:
                self.set_fw_load_status_msg('Connecting to drive')
                logger.info('Connecting to drive')
                self.set_fw_load_progress(25)
                try:
                    servo = self.connect_to_slave(target, servo_status_listener=False)
                    self.set_fw_load_progress(75)
                except Exception as e:
                    logger.error('Error connecting to drive through CAN: %s', e)
                    error_connecting = True

            if servo is not None and not error_connecting:
                # Check if bootloader is supported
                logger.info('Checking compatibility')
                self.set_fw_load_status_msg('Checking compatibility')
                prog_stat_1 = None
                try:
                    prog_stat_1 = servo.read(PROG_STAT_1, subnode=0)
                    is_bootloader_supported = True
                except Exception as e:
                    is_bootloader_supported = False

                self.set_fw_load_progress(85)

                if is_bootloader_supported:
                    # Check if file is .lfu
                    file_name, file_extension = os.path.splitext(fw_file)

                    if file_extension != '' and file_extension == '.sfu':
                        fd, lfu_path = tempfile.mkstemp(suffix=".lfu")
                        logger.debug('>> FD: {}. \n>> LFU PATH: {}.'.format(fd, lfu_path))

                        try:
                            # Convert the sfu file to lfu
                            logger.info('Converting sfu to lfu...')
                            self.set_fw_load_status_msg('Optimizing file')
                            logger.info('Optimizing file')
                            total_file_lines = count_file_lines(fw_file)
                            outfile = open(lfu_path, 'wb')
                            coco_in = open(fw_file, "r")
                            mcb = MCB()
                            copy_process = 0
                            self.set_fw_load_progress_total(total_file_lines)
                            self.set_fw_load_progress(0)
                            bin_node = ''
                            for line in coco_in:
                                if re.match("74 67 [0-4][0-4] 00 00 00 00 00 00 00", line) is not None:
                                    bin_node = line[6:8]

                                newline = '{} {}'.format(bin_node, line)
                                words = newline.split()

                                # Get command and address
                                subnode = int(words[0], 16)
                                cmd = int(words[2] + words[1], 16)
                                data = b''
                                num = 3
                                while num in range(3, len(words)):
                                    # load data MCB
                                    data = data + bytes([int(words[num], 16)])
                                    num = num + 1

                                # send message
                                node = 10
                                mcb.add_cmd(node, subnode, cmd, data, outfile)

                                self.set_fw_load_progress(copy_process)
                                copy_process += 1

                            outfile.close()
                            coco_in.close()
                            logger.info('Converted to lfu')
                        except Exception as e:
                            logger.error('Exception converting to lfu. {}'.format(e))

                    else:
                        lfu_path = fw_file

                    total_file_size = os.path.getsize(lfu_path) / BOOTLOADER_MSG_SIZE

                    # Check if Boot mode or App loaded
                    self.set_fw_load_progress_total(total_file_size)
                    self.set_fw_load_progress(0)

                    try:
                        device_type = servo.read(CIA301_DRV_ID_DEVICE_TYPE, subnode=0)
                        device_type = device_type & 0xFFFF
                    except Exception as e:
                        device_type = 0

                    if device_type == APPLICATION_LOADED_STATE:
                        # Drive profile
                        self.set_fw_load_status_msg('Entering Bootmode')
                        logger.info('Entering Bootmode')
                        # Enter in NMT pre-operational state.
                        servo.net.network.nmt.send_command(PROG_CTRL_STATE_FLASH)
                        # The drive will unlock the clear program command
                        password = 0x70636675

                        try:
                            servo.write(FORCE_BOOT, password, subnode=0)
                        except Exception as e:
                            pass
                    if prog_stat_1 == PROG_CTRL_STATE_START or prog_stat_1 == PROG_CTRL_STATE_FLASH:
                        # Write 0 to 0x1F51 to stop the app
                        try:
                            servo.write(PROG_STAT_1, PROG_CTRL_STATE_STOP, subnode=0)
                        except Exception as e:
                            pass
                    self.set_fw_load_status_msg('Setting up drive')
                    logger.info('Connected')
                    logger.info('Clearing program...')

                    prog_stat_1 = None
                    try:
                        prog_stat_1 = servo.read(PROG_STAT_1, subnode=0)
                        r = 0
                    except Exception as e:
                        r = -1

                    if r >= 0 and prog_stat_1 == PROG_CTRL_STATE_STOP:

                        try:
                            servo.write(PROG_STAT_1, PROG_CTRL_STATE_CLEAR, subnode=0)
                        except Exception as e:
                            pass

                        r = wait_for_register_value(servo, 0, PROG_STAT_1, PROG_CTRL_STATE_CLEAR)
                    if r >= 0:
                        try:
                            servo.write(PROG_STAT_1, PROG_CTRL_STATE_FLASH, subnode=0)
                        except Exception as e:
                            pass

                        r = wait_for_register_value(servo, 0, PROG_STAT_1, PROG_CTRL_STATE_FLASH)
                        if r < 0:
                            error_detected_msg = 'Error entering flashing mode'
                            logger.info(error_detected_msg)
                    else:
                        error_detected_msg = 'Error entering boot mode'
                        logger.error(error_detected_msg)

                    if error_detected_msg == '':
                        logger.info('Downloading program...')
                        image = open(lfu_path, "rb")
                        progress = 0
                        # Read image content in BOOTLOADER_MSG_SIZE
                        try:
                            error_downloading = False
                            servo.change_sdo_timeout(10)
                            self.set_fw_load_status_msg('Downloading firmware')
                            logger.info('Downloading firmware')
                            byte = image.read(1)
                            bytes_data = bytearray()
                            counter_blocks = 1
                            while not error_downloading:
                                bytes_data.extend(byte)
                                if counter_blocks == BOOTLOADER_MSG_SIZE:
                                    counter_blocks = 0
                                    try:
                                        servo.write(PROG_DL_1, bytes_data, subnode=0)
                                        r = 0
                                    except Exception as e:
                                        r = -1

                                    if r < 0:
                                        error_downloading = True
                                        error_detected_msg = 'An error occurred while downloading.'
                                    progress += 1
                                    self.set_fw_load_progress(progress)
                                    bytes_data = bytearray()
                                byte = image.read(1)
                                if not byte:
                                    break
                                counter_blocks += 1

                            if not error_downloading:
                                self.set_fw_load_status_msg('Flashing firmware')
                                logger.info("Download Finished!")
                                logger.info("Flashing firmware")
                                self.set_fw_load_progress_total(0)

                                try:
                                    servo.write(PROG_DL_1, bytes_data, subnode=0)
                                except Exception as e:
                                    pass

                                servo.change_sdo_timeout(CANOPEN_SDO_RESPONSE_TIMEOUT)
                        except Exception as e:
                            error_detected_msg = 'An error occurred while downloading.'
                            logger.error('Failed to download fw, reset might be needed. Exception {}.'.format(e))
                        try:
                            image.close()
                            logger.debug('Temp file deleted')
                        except Exception as e:
                            logger.warning('Could not remove temp file. Exception: {}'.format(e))

                    if error_detected_msg == '':
                        logger.info('Disable errors')
                        self.set_fw_load_errors_enabled(False)

                        logger.info("Flashing...")

                        try:
                            servo.write(PROG_STAT_1, PROG_CTRL_STATE_STOP, subnode=0)
                        except Exception as e:
                            pass
                        
                        logger.info('Waiting for the drive to respond...')
                        sleep(5)
                        initial_time = time()
                        time_diff = time() - initial_time
                        bool_timeout = False
                        while self.net_state != NET_STATE.CONNECTED and time_diff < RECONNECTION_TIMEOUT:
                            time_diff = time() - initial_time
                            sleep(0.5)
                        if not time_diff < RECONNECTION_TIMEOUT:
                            bool_timeout = True

                        logger.debug("Time waited for reconnection: ", time_diff, bool_timeout)
                        logger.debug("Net state after reconnection: ", self.net_state)

                        # Wait for drive to be available
                        sleep(5)

                        self.set_fw_load_status_msg('Starting program')
                        logger.info("Starting program")

                        try:
                            servo.write(PROG_STAT_1, PROG_CTRL_STATE_START, subnode=0)
                        except Exception as e:
                            pass

                        if not bool_timeout:
                            logger.info('Bootloader finished successfully!')
                            self.set_fw_load_status_msg('Bootloader finished successfully!')
                        else:
                            error_detected_msg = 'Could not recover drive'
                            logger.error(error_detected_msg)
                else:
                    # Bootloader not supported
                    error_detected_msg = 'Firmware and bootloader versions are not compatible. ' \
                                            'Use FTP Bootloader instead.'
            else:
                error_detected_msg = 'Failed to connect to the drive'
                logger.error("Error detected could not specify the drive.")
                if self.__connection is not None and not servo_connected:
                    self.teardown_connection()
                    logger.error('CANopen connection disconnected')
        except Exception as e:
            logger.error('Failed to load firmware. Exception: {}'.format(e))
            error_detected_msg = 'Failed to load firmware'
            if servo is not None and not servo_connected:
                self.disconnect_from_slave(servo)
            elif self.__connection is not None and not servo_connected:
                self.teardown_connection()
                logger.error('CANopen connection disconnected')
        try:
            if servo is not None and not servo_connected:
                self.disconnect_from_slave(servo)
            elif self.__connection is not None and not servo_connected:
                self.teardown_connection()
                logger.error('CANopen connection disconnected')
        except Exception as e:
            logger.error('Could not disconnect the drive. Exception {}.'.format(e))

        try:
            if lfu_path != fw_file:
                os.remove(lfu_path)
        except Exception as e:
            logger.warning('Could not remove {}. Exception: {}'.format(lfu_path, e))

        self.set_fw_load_errors_enabled(True)
        
        if error_detected_msg != '':
            raise ILFirmwareLoadError(error_detected_msg)

    def set_fw_load_status_msg(self, new_value):
        """ Updates the fw_load_status_msg value and triggers all the callbacks associated.

        Args:
            new_value: New value for the variable.

        """
        self.__fw_load_status_msg = new_value
        for callback in self.__observers_fw_load_status_msg:
            callback(new_value)

    def set_fw_load_progress(self, new_value):
        """ Updates the fw_load_progress value and triggers all the callbacks associated.

        Args:
            new_value: New value for the variable.

        """
        self.__fw_load_progress = new_value
        for callback in self.__observers_fw_load_progress:
            callback(new_value)

    def set_fw_load_progress_total(self, new_value):
        """ Updates the fw_load_progress_total value and triggers all the callbacks associated.

        Args:
            new_value: New value for the variable.

        """
        self.__fw_load_progress_total = new_value
        for callback in self.__observers_fw_load_progress_total:
            callback(new_value)

    def set_fw_load_errors_enabled(self, new_value):
        """ Updates the fw_load_errors_enabled value and triggers all the callbacks associated.

        Args:
            new_value: New value for the variable.

        """
        self.__fw_load_errors_enabled = new_value
        for callback in self.__observers_fw_load_errors_enabled:
            callback(new_value)

    def change_baudrate(self, target_node, vendor_id, product_code,
                        rev_number, serial_number, new_target_baudrate=None):
        """ Changes the node ID of a given target node ID.

        Args:
            target_node (int): Node ID of the targeted device.
            vendor_id (int): Vendor ID of the targeted device.
            product_code (int): Product code of the targeted device.
            rev_number (int): Revision number of the targeted device.
            serial_number (int): Serial number of the targeted device.
            new_target_baudrate (int): New baudrate for the targeted device.

        Returns:
            bool: Indicates if the operation was successful.

        """
        r = self.lss_switch_state_selective(vendor_id, product_code,
                                            rev_number, serial_number)
        if r < 0:
            self.__connection.lss.configure_bit_timing(
                CAN_BIT_TIMMING[new_target_baudrate].value
            )
            sleep(0.1)

            self.lss_store_configuration()

        else:
            return -1

        self.lss_reset_connection_nodes(target_node)
        logger.info('Baudrate changed to {}'.format(new_target_baudrate))
        return 0

    def change_node_id(self, target_node, vendor_id, product_code,
                       rev_number, serial_number, new_target_node=None):
        """ Changes the node ID of a given target node ID.

        Args:
            target_node (int): Node ID of the targeted device.
            vendor_id (int): Vendor ID of the targeted device.
            product_code (int): Product code of the targeted device.
            rev_number (int): Revision number of the targeted device.
            serial_number (int): Serial number of the targeted device.
            new_target_node (int): New node ID for the targeted device.

        Returns:
            bool: Indicates if the operation was successful.

        """
        r = self.lss_switch_state_selective(vendor_id, product_code,
                                            rev_number, serial_number)

        if r < 0:
            self.__connection.lss.configure_node_id(new_target_node)
            sleep(0.1)

            self.lss_store_configuration()

        else:
            return -1

        self.lss_reset_connection_nodes(target_node)
        logger.info('Node ID changed to {}'.format(new_target_node))
        return 0

    def lss_store_configuration(self):
        """ Stores the current configuration of the LSS"""
        self.__connection.lss.store_configuration()
        sleep(0.1)
        logger.info('Stored new configuration')
        self.__connection.lss.send_switch_state_global(
            self.__connection.lss.WAITING_STATE
        )

    def lss_switch_state_selective(self, vendor_id, product_code, rev_number, serial_number):
        """ Switches the state of the LSS to configuration state.
        
        Args:
            vendor_id (int): Vendor ID of the targeted device.
            product_code (int): Product code of the targeted device.
            rev_number (int): Revision number of the targeted device.
            serial_number (int): Serial number of the targeted device.

        Returns:
            bool: Boolean indicating if the operation was successful.

        """
        logger.debug("Switching LSS into CONFIGURATION state...")

        try:
            r = self.__connection.lss.send_lss_switch_state_selective(
                vendor_id,
                product_code,
                rev_number,
                serial_number,
            )
        except Exception as e:
            r = -1
            logger.error('LSS Timeout. Exception: %s', e)

        return r

    def lss_reset_connection_nodes(self, target_node):
        """ Resets the connection and starts node guarding for the connection nodes.

        Args:
            target_node (int): Node ID of the targeted device.

        """
        self.__connection.nodes[target_node].nmt.send_command(0x82)

        logger.debug("Wait until node is reset")
        sleep(0.5)

        logger.debug("Searching for nodes...")
        nodes = self.scan_slaves()

        for node_id in nodes:
            logger.info('Node found: %i', node_id)
            node = self.__connection.add_node(node_id, self.__eds)

        # Reset all nodes to default state
        self.__connection.lss.send_switch_state_global(
            self.__connection.lss.WAITING_STATE
        )

        self.__connection.nodes[target_node].nmt.start_node_guarding(1)

    def subscribe_to_network_status(self, cb):
        """ Subscribe to network state changes.

        Args:
            cb: Callback

        Returns:
            int: Assigned slot.
        """
        r = len(self.__observers_net_state)
        self.__observers_net_state.append(cb)
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

    @deprecated('subscribe_to_network_status')
    def net_state_subscribe(self, cb):
        """ Subscribe to network state changes.

        Args:
            cb: Callback

        Returns:
            int: Assigned slot.
        """
        r = len(self.__observers_net_state)
        self.__observers_net_state.append(cb)
        return r

    @deprecated('change_node_id and change_baudrate')
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
            bool_result = self.__connection.lss.send_lss_switch_state_selective(
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

    @deprecated(new_func_name='scan_slaves')
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
        sleep(0.05)
        return self.__connection.scanner.nodes

    @deprecated('connect_to_slave')
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

                self.servos.append(CanopenServo(self, node_id, node, dict,
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

    @deprecated('disconnect_from_slave')
    def disconnect(self):
        """ Disconnects the already established network. """
        try:
            self.stop_net_status_listener()
        except Exception as e:
            logger.error('Failed stopping net_status_listener. Exception: %s', e)

        try:
            for servo in self.servos:
                servo.stop_status_listener()
        except Exception as e:
            logger.error('Failed stopping drive status thread. Exception: %s', e)

        try:
            self.__connection.disconnect()
        except Exception as e:
            logger.error('Failed disconnecting. Exception: %s', e)
            raise_err(lib.IL_EFAIL, 'Failed disconnecting.')
    
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
        for callback in self.__observers_net_state:
            callback(self.__net_state)
