import contextlib
from enum import Enum
from time import sleep, time
from threading import Thread
from typing import Optional, Callable

from .register import CanopenRegister
from ingenialink.utils.mcb import MCB
from ingenialink.utils._utils import count_file_lines, wait_for_register_value
from ..exceptions import ILFirmwareLoadError, ILObjectNotExist, ILError
from can import CanError
from ..network import NET_PROT, NET_STATE, NET_DEV_EVT, Network
from .servo import CanopenServo, REG_ACCESS, REG_DTYPE, CANOPEN_SDO_RESPONSE_TIMEOUT

import re
import os
import canopen
import tempfile
import ingenialogger

logger = ingenialogger.get_logger(__name__)

PROG_STAT_1 = CanopenRegister(
    identifier="CIA302_BL_PROGRAM_CONTROL_1",
    units="",
    subnode=0,
    idx=0x1F51,
    subidx=0x01,
    cyclic="CONFIG",
    dtype=REG_DTYPE.U8,
    access=REG_ACCESS.RW,
)
PROG_DL_1 = CanopenRegister(
    identifier="CIA302_BL_PROGRAM_DATA",
    units="",
    subnode=0,
    idx=0x1F50,
    subidx=0x01,
    cyclic="CONFIG",
    dtype=REG_DTYPE.DOMAIN,
    access=REG_ACCESS.RW,
)
FORCE_BOOT = CanopenRegister(
    identifier="DRV_BOOT_COCO_FORCE",
    units="",
    subnode=0,
    idx=0x5EDE,
    subidx=0x00,
    cyclic="CONFIG",
    dtype=REG_DTYPE.U32,
    access=REG_ACCESS.WO,
)

CIA301_DRV_ID_DEVICE_TYPE = CanopenRegister(
    identifier="",
    units="",
    subnode=0,
    idx=0x1000,
    subidx=0x00,
    cyclic="CONFIG",
    dtype=REG_DTYPE.U32,
    access=REG_ACCESS.RO,
)

CANOPEN_SEND_FW_SDO_RESPONSE_TIMEOUT = 10  # Seconds
BOOTLOADER_MSG_SIZE = 256  # Size in Bytes
RECONNECTION_TIMEOUT = 180  # Seconds
POLLING_MAX_TRIES = 5  # Seconds

PROG_CTRL_STATE_STOP = 0x00
PROG_CTRL_STATE_START = 0x01
PROG_CTRL_STATE_CLEAR = 0x03
PROG_CTRL_STATE_FLASH = 0x80

APPLICATION_LOADED_STATE = 402

CAN_CHANNELS = {
    "kvaser": (0, 1),
    "pcan": ("PCAN_USBBUS1", "PCAN_USBBUS2"),
    "ixxat": (0, 1),
    "virtual": (0, 1),
}


class CAN_DEVICE(Enum):
    """CAN Device."""

    KVASER = "kvaser"
    PCAN = "pcan"
    IXXAT = "ixxat"
    VIRTUAL = "virtual"


class CAN_BAUDRATE(Enum):
    """Baudrates."""

    Baudrate_1M = 1000000
    """1 Mbit/s"""
    Baudrate_500K = 500000
    """500 Kbit/s"""
    Baudrate_250K = 250000
    """250 Kbit/s"""
    Baudrate_125K = 125000
    """125 Kbit/s"""
    Baudrate_100K = 100000
    """100 Kbit/s"""
    Baudrate_50K = 50000
    """50 Kbit/s"""


CAN_BIT_TIMMING = {
    CAN_BAUDRATE.Baudrate_1M: 0,
    CAN_BAUDRATE.Baudrate_500K: 2,
    CAN_BAUDRATE.Baudrate_250K: 3,
    CAN_BAUDRATE.Baudrate_125K: 4,
    CAN_BAUDRATE.Baudrate_100K: 5,
    CAN_BAUDRATE.Baudrate_50K: 6,
}


class NetStatusListener(Thread):
    """Network status listener thread to check if the drive is alive.

    Args:
        network (CanopenNetwork): Network instance of the CANopen communication.
        node (canopen.RemoteNode): Identifier for the targeted node ID.

    """

    def __init__(self, network, node):
        super(NetStatusListener, self).__init__()
        self.__network = network
        self.node = node
        self.__timestamp = self.node.nmt.timestamp
        self.__state = NET_STATE.CONNECTED
        self.__stop = False

    def run(self):
        while not self.__stop:
            if self.__timestamp == self.node.nmt.timestamp:
                if self.__state != NET_STATE.DISCONNECTED:
                    self.__network.status = NET_STATE.DISCONNECTED
                    self.__state = NET_STATE.DISCONNECTED
                    self.__network._notify_status(NET_DEV_EVT.REMOVED)
                else:
                    self.__network._reset_connection()
            else:
                if self.__state != NET_STATE.CONNECTED:
                    self.__network.status = NET_STATE.CONNECTED
                    self.__state = NET_STATE.CONNECTED
                    self.__network._notify_status(NET_DEV_EVT.ADDED)
                self.__timestamp = self.node.nmt.timestamp
            sleep(1.5)

    def stop(self):
        self.__stop = True


class CanopenNetwork(Network):
    """Network of the CANopen communication.

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
        self._connection = None
        self.__listeners_net_status = []
        self.__net_state = NET_STATE.DISCONNECTED

        self.__observers_net_state = []
        self.__observers_fw_load_status_msg = []
        self.__observers_fw_load_progress = []
        self.__observers_fw_load_errors_enabled = []

        self.__fw_load_status_msg = ""
        self.__fw_load_progress = 0
        self.__fw_load_errors_enabled = True

    def scan_slaves(self):
        """Scans for nodes in the network.

        Returns:
            list: Containing all the detected node IDs.

        """
        is_connection_created = False
        if self._connection is None:
            is_connection_created = True
            try:
                self._setup_connection()
            except ILError:
                self._teardown_connection()
                return []

        self._connection.scanner.reset()
        try:
            self._connection.scanner.search()
        except Exception as e:
            logger.error("Error searching for nodes. Exception: {}".format(e))
            logger.info("Resetting bus")
            if (
                self._connection is not None
                and self._connection.bus is not None
                and hasattr(self._connection.bus, "reset")
            ):
                self._connection.bus.reset()
        sleep(0.05)

        nodes = self._connection.scanner.nodes

        if is_connection_created:
            self._teardown_connection()

        return nodes

    def connect_to_slave(
        self,
        target,
        dictionary=None,
        servo_status_listener=False,
        net_status_listener=False,
    ):
        """Connects to a drive through a given target node ID.

        Args:
            target (int): Targeted node ID to be connected.
            dictionary (str): Path to the dictionary file.
            servo_status_listener (bool): Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener (bool): Toggle the listener of the network
                status, connection and disconnection.

        """
        nodes = self.scan_slaves()
        if len(nodes) < 1:
            raise ILError("Could not find any nodes in the network")

        self._setup_connection()
        if target in nodes:
            try:
                node = self._connection.add_node(target)

                node.nmt.start_node_guarding(1)

                servo = CanopenServo(
                    target, node, dictionary, servo_status_listener=servo_status_listener
                )

                if net_status_listener:
                    self.start_status_listener(servo)

                self.servos.append(servo)
                return servo
            except Exception as e:
                logger.error("Failed connecting to node %i. Exception: %s", target, e)
                raise ILError(
                    "Failed connecting to node {}. "
                    "Please check the connection settings and verify "
                    "the transceiver is properly connected.".format(target)
                )
        else:
            logger.error("Node id not found")
            raise ILError("Node id {} not found in the network.".format(target))

    def disconnect_from_slave(self, servo):
        """Disconnects the slave from the network.

        Args:
            servo (CanopenServo): Instance of the servo connected.

        """
        self.stop_status_listener(servo)
        servo.stop_status_listener()
        self.servos.remove(servo)
        if not self.servos:
            self._teardown_connection()

    def _setup_connection(self):
        """Creates a network interface object establishing an empty connection
        with all the network attributes already specified."""
        if self._connection is None:
            self._connection = canopen.Network()

            try:
                self._connection.connect(
                    bustype=self.__device, channel=self.__channel, bitrate=self.__baudrate
                )
            except CanError as e:
                logger.error("Transceiver not found in network. Exception: %s", e)
                raise ILError(
                    "Error connecting to the transceiver. "
                    "Please verify the transceiver "
                    "is properly connected."
                )
            except OSError as e:
                logger.error("Transceiver drivers not properly installed. Exception: %s", e)
                if hasattr(e, "winerror") and e.winerror == 126:
                    e.strerror = "Driver module not found. Drivers might not be properly installed."
                raise ILError(e)
            except Exception as e:
                logger.error("Failed trying to connect. Exception: %s", e)
                raise ILError("Failed trying to connect. {}".format(e))
        else:
            logger.info("Connection already established")

    def _teardown_connection(self):
        """Tears down the already established connection
        and deletes the network interface"""
        self._connection.disconnect()
        self._connection = None
        logger.info("Tear down connection.")

    def _reset_connection(self):
        """Resets the established CANopen network."""
        try:
            self._connection.disconnect()
        except BaseException as e:
            logger.error("Disconnection failed. Exception: %", e)

        try:
            for node in self._connection.scanner.nodes:
                self._connection.nodes[node].nmt.stop_node_guarding()
            if self._connection.bus:
                self._connection.bus.flush_tx_buffer()
                logger.info("Bus flushed")
        except Exception as e:
            logger.error("Could not stop guarding. Exception: %", e)

        try:
            self._connection.connect(
                bustype=self.__device, channel=self.__channel, bitrate=self.__baudrate
            )
            for servo in self.servos:
                node = self._connection.add_node(servo.target)
                node.nmt.start_node_guarding(1)
        except BaseException as e:
            logger.error("Connection failed. Exception: %s", e)

    def load_firmware(
        self,
        target: int,
        fw_file: str,
        callback_status_msg: Optional[Callable[[str], None]] = None,
        callback_progress: Optional[Callable[[int], None]] = None,
        callback_errors_enabled: Optional[callable] = None,
    ) -> None:
        """Loads a given firmware file to a target.

        .. warning ::
            It is needed to disconnect the drive(:func:`disconnect_from_slave`)
            after loading the firmware since the `Servo` object's data will
            become obsolete.

        Args:
            target: Targeted node ID to be loaded.
            fw_file: Path to the firmware file.
            callback_status_msg: Subscribed callback function for the status
                message when loading a firmware.
            callback_progress: Subscribed callback function for the live
                progress when loading a firmware.
            callback_errors_enabled: Subscribed callback function for
                knowing when to toggle the error detection when loading firmware.

        Raises:
            FileNotFoundError: Firmware file does not exist.
            ILFirmwareLoadError: The firmware load process fails with an error message.

        """
        if not os.path.isfile(fw_file):
            raise FileNotFoundError(f"Could not find {fw_file}.")

        servo = None
        for connected_servo in self.servos:
            if connected_servo.target == target:
                servo = connected_servo
        if not servo:
            raise ILFirmwareLoadError(f"Node {target} is not connected.")

        logger.info("Checking compatibility")
        if callback_status_msg:
            callback_status_msg("Checking compatibility")
        try:
            initial_status = servo.read(PROG_STAT_1, subnode=0)
        except ILError as e:
            raise ILFirmwareLoadError(
                "Firmware and bootloader versions are not compatible. Use FTP Bootloader instead."
            ) from e

        _, file_extension = os.path.splitext(fw_file)
        if file_extension == ".sfu":
            fw_file = self.__optimize_firmware_file(fw_file, callback_status_msg)
        self.__force_boot(servo, callback_status_msg)
        self.__program_control_to_flash(initial_status, servo, callback_status_msg)
        self.__send_fw_file(fw_file, servo, callback_status_msg, callback_progress)
        self.__program_control_from_flash_to_start(servo, callback_status_msg)
        self.__wait_for_app_restart(servo, callback_status_msg)
        logger.info("Bootloader finished successfully!")
        if callback_status_msg:
            callback_status_msg("Bootloader finished successfully!")

    def __force_boot(
        self, servo: CanopenServo, callback_status_msg: Optional[Callable[[str], None]]
    ) -> None:
        """Force boot, if drive is already in boot, do nothing

        Args:
            servo: target drive

        """
        device_type = servo.read(CIA301_DRV_ID_DEVICE_TYPE, subnode=0)
        device_type = device_type & 0xFFFF
        if device_type == APPLICATION_LOADED_STATE:
            if callback_status_msg:
                callback_status_msg("Entering Bootmode")
            logger.info("Entering Bootmode")
            # Drive profile
            # Enter in NMT pre-operational state.
            self._connection.nmt.send_command(PROG_CTRL_STATE_FLASH)
            # The drive will unlock the clear program command
            password = 0x70636675
            servo.write(FORCE_BOOT, password, subnode=0)

    @staticmethod
    def __program_control_to_flash(
        initial_status: int,
        servo: CanopenServo,
        callback_status_msg: Optional[Callable[[str], None]],
    ) -> None:
        """Change program control status to flash.

        Args:
            initial_status: program control initial status
            servo: target drive

        Raises:
            ILFirmwareLoadError: Program control status does not change

        """
        if callback_status_msg:
            callback_status_msg("Setting up drive")
        target_status_list = (
            [PROG_CTRL_STATE_STOP] if initial_status != PROG_CTRL_STATE_STOP else []
        )
        target_status_list += [PROG_CTRL_STATE_CLEAR, PROG_CTRL_STATE_FLASH]
        logger.info("Clearing program...")
        for target_status in target_status_list:
            servo.write(PROG_STAT_1, target_status, subnode=0)
            if not wait_for_register_value(servo, 0, PROG_STAT_1, target_status):
                raise ILFirmwareLoadError(f"Error setting program control to 0x{target_status:X}")

    @staticmethod
    def __program_control_from_flash_to_start(
        servo: CanopenServo, callback_status_msg: Optional[Callable[[str], None]]
    ):
        """Change program control status from flash to start.

        Args:
            servo: target drive

        """
        if callback_status_msg:
            callback_status_msg("Flashing firmware")
        with contextlib.suppress(ILError):
            servo.write(PROG_STAT_1, PROG_CTRL_STATE_STOP, subnode=0)
            servo.write(PROG_STAT_1, PROG_CTRL_STATE_START, subnode=0)
        logger.info("Flashing firmware...")

    @staticmethod
    def __wait_for_app_restart(
        servo: CanopenServo, callback_status_msg: Optional[Callable[[str], None]]
    ):
        """Wait drive

        Args:
            servo: target drive

        Raises:
            ILFirmwareLoadError: App can't start after 180 seconds

        """
        if callback_status_msg:
            callback_status_msg("Starting program")
        logger.info("Waiting for the drive to be available.")
        initial_time = time()
        while (time() - initial_time) < RECONNECTION_TIMEOUT:
            with contextlib.suppress(ILError):
                servo.read(servo.STATUS_WORD_REGISTERS)
                return
            sleep(0.5)
        raise ILFirmwareLoadError("Could not recover drive")

    @staticmethod
    def __optimize_firmware_file(sfu_file, callback_status_msg: Optional[Callable[[str], None]]):
        """Convert SFU file to LFU to optimize the firmware loading.

        Args:
            sfu_file: target SFU file

        Returns:
            LFU file path
        """
        mcb = MCB()
        total_file_lines = count_file_lines(sfu_file)
        # Convert the sfu file to lfu
        logger.info("Converting sfu to lfu...")
        logger.info("Optimizing file")
        if callback_status_msg:
            callback_status_msg("Optimizing file")
        lfu_file_d, lfu_path = tempfile.mkstemp(suffix=".lfu")
        with open(lfu_path, "wb") as lfu_file:
            with open(sfu_file, "r") as coco_in:
                bin_node = ""
                current_progress = 0
                node = 10
                for copy_process, line in enumerate(coco_in):
                    if re.match(r"74 67 [0-4][0-4] 00 00 00 00 00 00 00", line) is not None:
                        bin_node = line[6:8]

                    newline = f"{bin_node} {line}"
                    words = newline.split()

                    # Get command and address
                    subnode = int(words[0], 16)
                    cmd = int(words[2] + words[1], 16)
                    data = b""
                    num = 3
                    while num in range(3, len(words)):
                        # load data MCB
                        data += bytes([int(words[num], 16)])
                        num += 1

                    # send message
                    mcb.add_cmd(node, subnode, cmd, data, lfu_file)
                    new_progress = int(copy_process * 100 / total_file_lines)
                    if new_progress != current_progress:
                        current_progress = new_progress
                        logger.info(f"Optimizing firmware file in progress: {current_progress}%")
        logger.info("Converted to lfu")
        return lfu_path

    @staticmethod
    def __send_fw_file(
        fw_file: str,
        servo: CanopenServo,
        callback_status_msg: Optional[Callable[[str], None]],
        callback_progress: Optional[Callable[[int], None]],
    ):
        """Send firmware file to drive with SDOs

        Args:
            fw_file: target firmware file
            servo: target drive

        """
        total_file_size = os.path.getsize(fw_file) / BOOTLOADER_MSG_SIZE
        image = open(fw_file, "rb")
        servo._change_sdo_timeout(CANOPEN_SEND_FW_SDO_RESPONSE_TIMEOUT)
        logger.info("Downloading firmware")
        if callback_status_msg:
            callback_status_msg("Downloading firmware")
        counter = 0
        progress = 0
        while byte := image.read(BOOTLOADER_MSG_SIZE):
            servo.write(PROG_DL_1, byte, subnode=0)
            counter += 1
            new_progress = int(counter * 100 / total_file_size)
            if progress != new_progress:
                progress = new_progress
                logger.info(f"Download firmware in progress: {progress}%")
                if callback_progress:
                    callback_progress(progress)
        logger.info("Download Finished!")
        servo._change_sdo_timeout(CANOPEN_SDO_RESPONSE_TIMEOUT)

    def __set_fw_load_status_msg(self, new_value):
        """Updates the fw_load_status_msg value and triggers
        all the callbacks associated.

        Args:
            new_value: New value for the variable.

        """
        self.__fw_load_status_msg = new_value
        for callback in self.__observers_fw_load_status_msg:
            callback(new_value)

    def __set_fw_load_progress(self, new_value):
        """Updates the fw_load_progress value and triggers
        all the callbacks associated.

        Args:
            new_value: New value for the variable.

        """
        self.__fw_load_progress = new_value
        for callback in self.__observers_fw_load_progress:
            callback(new_value)

    def __set_fw_load_errors_enabled(self, new_value):
        """Updates the fw_load_errors_enabled value and triggers
        all the callbacks associated.

        Args:
            new_value: New value for the variable.

        """
        self.__fw_load_errors_enabled = new_value
        for callback in self.__observers_fw_load_errors_enabled:
            callback(new_value)

    def change_baudrate(
        self, target_node, new_target_baudrate, vendor_id, product_code, rev_number, serial_number
    ):
        """Changes the node ID of a given target node ID.

        .. note::
            The servo must be disconnected after this operation in order
            to make the changes visible and update all the internal data.
            It is also needed a power cycle of the servo otherwise the
            changes will not be applied.

        Args:
            target_node (int): Node ID of the targeted device.
            new_target_baudrate (CAN_BAUDRATE): New baudrate for the targeted device.
            vendor_id (int): Vendor ID of the targeted device.
            product_code (int): Product code of the targeted device.
            rev_number (int): Revision number of the targeted device.
            serial_number (int): Serial number of the targeted device.

        Returns:
            bool: Indicates if the operation was successful.

        """
        if self._connection is None:
            raise ILObjectNotExist("CAN connection was not established.")

        try:
            logger.debug("Switching LSS into CONFIGURATION state...")
            r = self._connection.lss.send_switch_state_selective(
                vendor_id,
                product_code,
                rev_number,
                serial_number,
            )
            if r >= 0:
                self._connection.lss.configure_bit_timing(CAN_BIT_TIMMING[new_target_baudrate])
                sleep(0.1)

                self._lss_store_configuration()
            else:
                raise ILError("Error switching lss to selective state. Error code: {}".format(r))
        finally:
            self._lss_reset_connection_nodes(target_node)
            logger.info("Baudrate changed to {}".format(new_target_baudrate))

    def change_node_id(
        self, target_node, new_target_node, vendor_id, product_code, rev_number, serial_number
    ):
        """Changes the node ID of a given target node ID.

        .. note::
            The servo must be disconnected after this operation in order
            to make the changes visible and update all the internal data.

        Args:
            target_node (int): Node ID of the targeted device.
            new_target_node (int): New node ID for the targeted device.
            vendor_id (int): Vendor ID of the targeted device.
            product_code (int): Product code of the targeted device.
            rev_number (int): Revision number of the targeted device.
            serial_number (int): Serial number of the targeted device.

        Returns:
            bool: Indicates if the operation was successful.

        """
        if self._connection is None:
            raise ILObjectNotExist("CAN connection was not established.")

        try:
            logger.debug("Switching LSS into CONFIGURATION state...")
            r = self._connection.lss.send_switch_state_selective(
                vendor_id,
                product_code,
                rev_number,
                serial_number,
            )
            if r >= 0:
                self._connection.lss.configure_node_id(new_target_node)
                sleep(0.1)

                self._lss_store_configuration()

            else:
                raise ILError("Error switching lss to selective state. Error code: {}".format(r))
        finally:
            self._lss_reset_connection_nodes(target_node)
            logger.info("Node ID changed to {}".format(new_target_node))

    def _lss_store_configuration(self):
        """Stores the current configuration of the LSS"""
        self._connection.lss.store_configuration()
        sleep(0.1)
        logger.info("Stored new configuration")
        self._connection.lss.send_switch_state_global(self._connection.lss.WAITING_STATE)

    def _lss_reset_connection_nodes(self, target_node):
        """Resets the connection and starts node guarding for the connection nodes.

        Args:
            target_node (int): Node ID of the targeted device.

        """
        self._connection.nodes[target_node].nmt.send_command(0x82)

        logger.debug("Wait until node is reset")
        sleep(0.5)

        for servo in self.servos:
            logger.info("Node connected: %i", servo.target)
            node = self._connection.add_node(servo.target)

        # Reset all nodes to default state
        self._connection.lss.send_switch_state_global(self._connection.lss.WAITING_STATE)

        self._connection.nodes[target_node].nmt.start_node_guarding(1)

    def subscribe_to_status(self, callback):
        """Subscribe to network state changes.

        Args:
            callback (function): Callback function.

        """
        if callback in self.__observers_net_state:
            logger.info("Callback already subscribed.")
            return
        self.__observers_net_state.append(callback)

    def unsubscribe_from_status(self, callback):
        """Unsubscribe from network state changes.

        Args:
            callback (function): Callback function.

        """
        if callback not in self.__observers_net_state:
            logger.info("Callback not subscribed.")
            return
        self.__observers_net_state.remove(callback)

    def _notify_status(self, status):
        for callback in self.__observers_net_state:
            callback(status)

    def is_listener_started(self, servo):
        for listener in self.__listeners_net_status:
            if listener.node.id == servo.node.id:
                return True
        return False

    def start_status_listener(self, servo):
        """Start monitoring network events (CONNECTION/DISCONNECTION)."""
        if self.is_listener_started(servo):
            logger.info(f"Listener on node {servo.node.id} is already started.")
            return
        listener = NetStatusListener(self, servo.node)
        listener.start()
        self.__listeners_net_status.append(listener)

    def stop_status_listener(self, servo):
        """Stops the NetStatusListener from listening to the drive."""
        try:
            for node_id, node_obj in self._connection.nodes.items():
                if node_id == servo.node.id:
                    node_obj.nmt.stop_node_guarding()
        except Exception as e:
            logger.error("Could not stop node guarding. Exception: %s", str(e))
        servo_listener = None
        for listener in self.__listeners_net_status:
            if listener.node.id == servo.node.id and listener.is_alive:
                listener.stop()
                listener.join()
                servo_listener = listener
        if servo_listener is not None:
            self.__listeners_net_status.remove(servo_listener)

    @property
    def device(self):
        """CAN_DEVICE: Current device of the network."""
        return self.__device

    @property
    def channel(self):
        """int: Current device of the network."""
        return self.__channel

    @property
    def baudrate(self):
        """int: Current baudrate of the network."""
        return self.__baudrate

    @property
    def network(self):
        """canopen.Network: Returns the instance of the CANopen Network."""
        return self._connection

    @property
    def protocol(self):
        """NET_PROT: Obtain network protocol."""
        return NET_PROT.CAN

    @property
    def status(self):
        """NET_STATE: Network state."""
        return self.__net_state

    @status.setter
    def status(self, new_state):
        self.__net_state = new_state
