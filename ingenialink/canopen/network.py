import contextlib
import os
import platform
import re
import tempfile
from collections import OrderedDict, defaultdict
from enum import Enum
from threading import Thread
from time import sleep
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

RUNNING_ON_WINDOWS = platform.system() == "Windows"

import canopen
import ingenialogger
from can import CanError

if RUNNING_ON_WINDOWS:
    from can.interfaces.ixxat.exceptions import VCIError
else:
    VCIError = None
from canopen import Network as NetworkLib

from ingenialink.canopen.register import CanopenRegister
from ingenialink.canopen.servo import (
    CANOPEN_SDO_RESPONSE_TIMEOUT,
    REG_ACCESS,
    REG_DTYPE,
    CanopenServo,
)
from ingenialink.exceptions import ILError, ILFirmwareLoadError, ILObjectNotExist
from ingenialink.network import NET_DEV_EVT, NET_PROT, NET_STATE, Network, SlaveInfo
from ingenialink.utils._utils import convert_bytes_to_dtype
from ingenialink.utils.mcb import MCB

logger = ingenialogger.get_logger(__name__)

PROG_STAT_1 = CanopenRegister(
    idx=0x1F51,
    subidx=0x01,
    cyclic="CONFIG",
    dtype=REG_DTYPE.U8,
    access=REG_ACCESS.RW,
    identifier="CIA302_BL_PROGRAM_CONTROL_1",
    subnode=0,
)
PROG_DL_1 = CanopenRegister(
    idx=0x1F50,
    subidx=0x01,
    cyclic="CONFIG",
    dtype=REG_DTYPE.DOMAIN,
    access=REG_ACCESS.RW,
    identifier="CIA302_BL_PROGRAM_DATA",
    subnode=0,
)
FORCE_BOOT = CanopenRegister(
    idx=0x5EDE,
    subidx=0x00,
    cyclic="CONFIG",
    dtype=REG_DTYPE.U32,
    access=REG_ACCESS.WO,
    identifier="DRV_BOOT_COCO_FORCE",
    subnode=0,
)

CIA301_DRV_ID_DEVICE_TYPE = CanopenRegister(
    idx=0x1000,
    subidx=0x00,
    cyclic="CONFIG",
    dtype=REG_DTYPE.U32,
    access=REG_ACCESS.RO,
    identifier="",
    subnode=0,
)

CANOPEN_BOTT_NODE_GUARDING_PERIOD = 5
CANOPEN_SEND_FW_SDO_RESPONSE_TIMEOUT = 10  # Seconds
BOOTLOADER_MSG_SIZE = 256  # Size in Bytes
RECONNECTION_TIMEOUT = 180  # Seconds
POLLING_MAX_TRIES = 5  # Seconds

PROG_CTRL_STATE_STOP = 0x00
PROG_CTRL_STATE_START = 0x01
PROG_CTRL_STATE_CLEAR = 0x03
PROG_CTRL_STATE_FLASH = 0x80

APPLICATION_LOADED_STATE = 402

CAN_CHANNELS: Dict[str, Union[Tuple[int, int], Tuple[str, str]]] = {
    "kvaser": (0, 1),
    "pcan": ("PCAN_USBBUS1", "PCAN_USBBUS2"),
    "ixxat": (0, 1),
    "virtual": (0, 1),
    "socketcan": ("can0", "can1"),
}


class CAN_DEVICE(Enum):
    """CAN Device."""

    KVASER = "kvaser"
    PCAN = "pcan"
    IXXAT = "ixxat"
    VIRTUAL = "virtual"
    SOCKETCAN = "socketcan"


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
        network: Network instance of the CANopen communication.

    """

    def __init__(self, network: "CanopenNetwork"):
        super(NetStatusListener, self).__init__()
        self.__network = network
        self.__stop = False

    def run(self) -> None:
        timestamps = {}
        if self.__network._connection is None:
            return
        while not self.__stop:
            for node_id, node in list(self.__network._connection.nodes.items()):
                sleep(1.5)
                current_timestamp = node.nmt.timestamp
                if node_id not in timestamps:
                    timestamps[node_id] = current_timestamp
                    continue
                is_alive = current_timestamp != timestamps[node_id]
                servo_state = self.__network._get_servo_state(node_id)
                if is_alive:
                    if servo_state != NET_STATE.CONNECTED:
                        self.__network._notify_status(node_id, NET_DEV_EVT.ADDED)
                        self.__network._set_servo_state(node_id, NET_STATE.CONNECTED)
                    timestamps[node_id] = node.nmt.timestamp
                elif servo_state == NET_STATE.DISCONNECTED:
                    self.__network._reset_connection()
                else:
                    self.__network._notify_status(node_id, NET_DEV_EVT.REMOVED)
                    self.__network._set_servo_state(node_id, NET_STATE.DISCONNECTED)

    def stop(self) -> None:
        self.__stop = True


class CanopenNetwork(Network):
    """Network of the CANopen communication.

    Args:
        device: Targeted device to connect.
        channel: Targeted channel number of the transceiver.
        baudrate: Baudrate to communicate through.

    """

    DRIVE_INFO_INDEX = 0x1018
    PRODUCT_CODE_SUB_IX = 2
    REVISION_NUMBER_SUB_IX = 3

    def __init__(
        self,
        device: CAN_DEVICE,
        channel: int = 0,
        baudrate: CAN_BAUDRATE = CAN_BAUDRATE.Baudrate_1M,
    ):
        super(CanopenNetwork, self).__init__()
        self.servos: List[CanopenServo] = []
        self.__device = device.value
        self.__channel: Union[int, str] = CAN_CHANNELS[self.__device][channel]
        self.__baudrate = baudrate.value
        self._connection: Optional[NetworkLib] = None
        self.__net_state = NET_STATE.DISCONNECTED
        self.__servos_state: Dict[int, NET_STATE] = {}
        self.__listener_net_status: Optional[NetStatusListener] = None
        self.__observers_net_state: Dict[int, List[Callable[[NET_DEV_EVT], Any]]] = defaultdict(
            list
        )
        self.__observers_fw_load_status_msg: List[Callable[[str], Any]] = []
        self.__observers_fw_load_progress: List[Callable[[int], Any]] = []
        self.__observers_fw_load_errors_enabled: List[Callable[[bool], Any]] = []

        self.__fw_load_status_msg = ""
        self.__fw_load_progress = 0
        self.__fw_load_errors_enabled = True

    def scan_slaves(self) -> List[int]:
        """Scans for nodes in the network.

        Returns:
            Containing all the detected node IDs.

        """
        is_connection_created = False
        if self._connection is None:
            is_connection_created = True
            try:
                self._setup_connection()
            except ILError:
                self._teardown_connection()
                return []

        if self._connection is None:
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

        return nodes  # type: ignore [no-any-return]

    def scan_slaves_info(self) -> OrderedDict[int, SlaveInfo]:
        """Scans for nodes in the network and return an ordered dict with the slave information.

        Returns:
            Ordered dict with the slave information.

        """
        connected_slaves = {servo.target: servo.node for servo in self.servos}
        slave_info: OrderedDict[int, SlaveInfo] = OrderedDict()
        try:
            slaves = self.scan_slaves()
        except ILError:
            return slave_info

        is_connection_created = False
        if self._connection is None:
            is_connection_created = True
            try:
                self._setup_connection()
            except ILError:
                self._teardown_connection()
                return slave_info

        if self._connection is None:
            return slave_info

        for slave_id in slaves:
            if slave_id not in connected_slaves:
                node = self._connection.add_node(slave_id)
            else:
                node = connected_slaves[slave_id]
            product_code = convert_bytes_to_dtype(
                node.sdo.upload(self.DRIVE_INFO_INDEX, self.PRODUCT_CODE_SUB_IX), REG_DTYPE.U32
            )
            revision_number = convert_bytes_to_dtype(
                node.sdo.upload(self.DRIVE_INFO_INDEX, self.REVISION_NUMBER_SUB_IX), REG_DTYPE.U32
            )
            slave_info[slave_id] = SlaveInfo(int(product_code), int(revision_number))

        if is_connection_created:
            self._teardown_connection()
        return slave_info

    def connect_to_slave(  # type: ignore [override]
        self,
        target: int,
        dictionary: str,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ) -> CanopenServo:
        """Connects to a drive through a given target node ID.

        Args:
            target: Targeted node ID to be connected.
            dictionary: Path to the dictionary file.
            servo_status_listener: Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener: Toggle the listener of the network
                status, connection and disconnection.

        """
        nodes = self.scan_slaves()
        if len(nodes) < 1:
            raise ILError("Could not find any nodes in the network")

        self._setup_connection()
        if self._connection is None:
            raise ILError("Connection has not been established")
        if target in nodes:
            try:
                node = self._connection.add_node(target)

                node.nmt.start_node_guarding(1)

                servo = CanopenServo(
                    target, node, dictionary, servo_status_listener=servo_status_listener
                )
                self.servos.append(servo)
                self._set_servo_state(target, NET_STATE.CONNECTED)
                if net_status_listener:
                    self.start_status_listener()
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

    def disconnect_from_slave(self, servo: CanopenServo) -> None:  # type: ignore [override]
        """Disconnects the slave from the network.

        Args:
            servo: Instance of the servo connected.

        """
        self.stop_status_listener()
        servo.stop_status_listener()
        self.servos.remove(servo)
        if not self.servos:
            self._teardown_connection()

    def _setup_connection(self) -> None:
        """Creates a network interface object establishing an empty connection
        with all the network attributes already specified."""
        if self._connection is None:
            self._connection = canopen.Network()
            connection_args = {
                "bustype": self.__device,
                "channel": self.__channel,
                "bitrate": self.__baudrate,
            }
            if self.__device == CAN_DEVICE.PCAN.value:
                connection_args["auto_reset"] = True
            try:
                self._connection.connect(**connection_args)
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

    def _teardown_connection(self) -> None:
        """Tears down the already established connection
        and deletes the network interface"""
        if self._connection is None:
            logger.warning("Can not disconnect. The connection is not established yet.")
            return
        self._connection.disconnect()
        self._connection = None
        logger.info("Tear down connection.")

    def _reset_connection(self) -> None:
        """Resets the established CANopen network.

        Raises:
            ILError: If the connection was not established yet.
        """
        if self._connection is None:
            raise ILError("Can not reset connection. The connection is not established yet.")
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

    def load_firmware(  # type: ignore [override]
        self,
        target: int,
        fw_file: str,
        callback_status_msg: Optional[Callable[[str], None]] = None,
        callback_progress: Optional[Callable[[int], None]] = None,
        callback_errors_enabled: Optional[Callable[[bool], None]] = None,
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
        servo = self.__load_fw_checks(target, fw_file, callback_status_msg)
        start_network_listener_after_reconnect = self.is_listener_started()
        start_servo_listener_after_reconnect = servo.is_listener_started()
        self.stop_status_listener()
        servo.stop_status_listener()
        initial_status = servo.read(PROG_STAT_1, subnode=0)
        _, file_extension = os.path.splitext(fw_file)
        if file_extension == ".sfu":
            fw_file = self.__optimize_firmware_file(fw_file, callback_status_msg)
        self.__force_boot(servo, callback_status_msg)
        self.__program_control_to_flash(int(initial_status), servo, callback_status_msg)
        try:
            self.__send_fw_file(fw_file, servo, callback_status_msg, callback_progress)
            self.__program_control_to_stop(servo, callback_status_msg)
            self.__program_control_to_start(servo, callback_status_msg)
        finally:
            if file_extension == ".sfu":
                os.remove(fw_file)
        logger.info("Bootloader finished successfully!")
        if callback_status_msg:
            callback_status_msg("Bootloader finished successfully!")
        if start_network_listener_after_reconnect:
            self.start_status_listener()
        if start_servo_listener_after_reconnect:
            servo.start_status_listener()

    def __load_fw_checks(
        self, target: int, fw_file: str, callback_status_msg: Optional[Callable[[str], None]] = None
    ) -> CanopenServo:
        """Checks prior to firmware upload and return the target CanopenServo instance

        Args:
            target: Targeted node ID to be loaded.
            fw_file: Path to the firmware file.
            callback_status_msg: Subscribed callback function for the status message

        Returns:
            Target servo

        Raises:
            FileNotFoundError: Firmware file does not exist.
            ILFirmwareLoadError: The drive is not connected.
            ILFirmwareLoadError: Firmware and bootloader versions are not compatible.

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
            servo.read(PROG_STAT_1, subnode=0)
        except ILError as e:
            raise ILFirmwareLoadError(
                "Firmware and bootloader versions are not compatible. Use FTP Bootloader instead."
            ) from e
        return servo

    def __force_boot(
        self, servo: CanopenServo, callback_status_msg: Optional[Callable[[str], None]]
    ) -> None:
        """Force boot, if drive is already in boot, do nothing

        Args:
            servo: target drive
            callback_status_msg: Subscribed callback function for the status message

        Raises:
            ILError: If the connection was not established yet.

        """
        if self._connection is None:
            raise ILError("Can not force boot. The connection is not established yet.")
        device_type = int(servo.read(CIA301_DRV_ID_DEVICE_TYPE, subnode=0))
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

    def __program_control_to_flash(
        self,
        initial_status: int,
        servo: CanopenServo,
        callback_status_msg: Optional[Callable[[str], None]],
    ) -> None:
        """Change program control status to flash.

        Args:
            initial_status: program control initial status
            servo: target drive
            callback_status_msg: Subscribed callback function for the status message

        Raises:
            ILFirmwareLoadError: Program control status does not change

        """
        if callback_status_msg:
            callback_status_msg("Setting up drive")
        target_status_list = [
            PROG_CTRL_STATE_START,
            PROG_CTRL_STATE_STOP,
            PROG_CTRL_STATE_CLEAR,
            PROG_CTRL_STATE_FLASH,
        ]
        status_index = target_status_list.index(initial_status) + 1
        logger.info("Clearing program...")
        for target_status in target_status_list[status_index:]:
            servo.write(PROG_STAT_1, target_status, subnode=0)
            if not self.__wait_for_register_value(servo, 0, PROG_STAT_1, target_status):
                raise ILFirmwareLoadError(f"Error setting program control to 0x{target_status:X}")

    @staticmethod
    def __wait_for_register_value(
        servo: CanopenServo,
        subnode: int,
        register: CanopenRegister,
        expected_value: Union[int, float, str],
    ) -> bool:
        """Waits for the register to reach a value.

        Args:
            servo: Instance of the servo to be used.
            subnode: Target subnode.
            register: Register to be read.
            expected_value: Expected value for the given register.

        Returns:
            True if values is reached, else False
        """
        logger.debug(f"Waiting for register {register} to return <{expected_value}>")
        num_tries = 0
        value = None
        while num_tries < POLLING_MAX_TRIES:
            with contextlib.suppress(ILError):
                value = servo.read(register, subnode=subnode)
            if value == expected_value:
                logger.debug(f"Success. Read value {value}. Num tries {num_tries}")
                return True
            num_tries += 1
            logger.debug(f"Trying again {num_tries}. value {value}.")
            sleep(1)
        return False

    @staticmethod
    def __program_control_to_stop(
        servo: CanopenServo, callback_status_msg: Optional[Callable[[str], None]]
    ) -> None:
        """Change program control status to stop.

        Args:
            servo: target drive
            callback_status_msg: Subscribed callback function for the status message

        Raises:
            ILFirmwareLoadError: Drive does not respond

        """
        if callback_status_msg:
            callback_status_msg("Flashing firmware")
        logger.info("Flashing firmware")
        with contextlib.suppress(ILError):
            servo.write(PROG_STAT_1, PROG_CTRL_STATE_STOP, subnode=0)
        try:
            servo.node.nmt.start_node_guarding(CANOPEN_BOTT_NODE_GUARDING_PERIOD)
        except VCIError as e:
            # This error is a specific error for ixxat transceivers
            raise ILFirmwareLoadError("An error occurred when starting the node guarding.") from e
        try:
            servo.node.nmt.wait_for_heartbeat(timeout=RECONNECTION_TIMEOUT)
        except canopen.nmt.NmtError as e:
            raise ILFirmwareLoadError("Could not recover drive") from e
        finally:
            servo.node.nmt.stop_node_guarding()

    @staticmethod
    def __program_control_to_start(
        servo: CanopenServo, callback_status_msg: Optional[Callable[[str], None]]
    ) -> None:
        """Change program control status to start.

        Args:
            servo: target drive
            callback_status_msg: Subscribed callback function for the status message

        Raises:
            ILFirmwareLoadError: Drive does not respond

        """
        if callback_status_msg:
            callback_status_msg("Starting program")
        logger.info("Starting program")
        with contextlib.suppress(ILError):
            servo.write(PROG_STAT_1, PROG_CTRL_STATE_START, subnode=0)
        try:
            servo.node.nmt.wait_for_bootup(timeout=RECONNECTION_TIMEOUT)
        except canopen.nmt.NmtError as e:
            raise ILFirmwareLoadError("Could not recover drive") from e

    @staticmethod
    def __optimize_firmware_file(
        sfu_file: str, callback_status_msg: Optional[Callable[[str], None]]
    ) -> str:
        """Convert SFU file to LFU to optimize the firmware loading.

        Args:
            sfu_file: target SFU file
            callback_status_msg: Subscribed callback function for the status message

        Returns:
            LFU file path

        """
        mcb = MCB()
        with open(sfu_file, "r") as temp_file:
            total_file_lines = sum(1 for _ in temp_file)
        # Convert the sfu file to lfu
        logger.info("Converting sfu to lfu...")
        logger.info("Optimizing file")
        if callback_status_msg:
            callback_status_msg("Optimizing file")
        lfu_file_d, lfu_path = tempfile.mkstemp(suffix=".lfu", text=True)
        os.close(lfu_file_d)
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
    ) -> None:
        """Send firmware file to drive with SDOs

        Args:
            fw_file: target firmware file
            servo: target drive
            callback_status_msg: Subscribed callback function for the status message
            callback_progress: Subscribed callback function for the live progress.

        Raises:
            ILFirmwareLoadError: Drive does not respond

        """
        total_file_size = os.path.getsize(fw_file) / BOOTLOADER_MSG_SIZE
        servo._change_sdo_timeout(CANOPEN_SEND_FW_SDO_RESPONSE_TIMEOUT)
        logger.info("Downloading firmware")
        if callback_status_msg:
            callback_status_msg("Downloading firmware")
        counter = 0
        progress = 0
        with open(fw_file, "rb") as image:
            byte = image.read(BOOTLOADER_MSG_SIZE)
            while byte:
                try:
                    servo.write(PROG_DL_1, byte, subnode=0)
                except ILError as e:
                    raise ILFirmwareLoadError(
                        "An error occurred while downloading. Check firmware file is correct."
                    ) from e
                counter += 1
                new_progress = int(counter * 100 / total_file_size)
                if progress != new_progress:
                    progress = new_progress
                    logger.info(f"Download firmware in progress: {progress}%")
                    if callback_progress:
                        callback_progress(progress)
                byte = image.read(BOOTLOADER_MSG_SIZE)
        logger.info("Download Finished!")
        servo._change_sdo_timeout(CANOPEN_SDO_RESPONSE_TIMEOUT)

    def __set_fw_load_status_msg(self, new_value: str) -> None:
        """Updates the fw_load_status_msg value and triggers
        all the callbacks associated.

        Args:
            new_value: New value for the variable.

        """
        self.__fw_load_status_msg = new_value
        for callback in self.__observers_fw_load_status_msg:
            callback(new_value)

    def __set_fw_load_progress(self, new_value: int) -> None:
        """Updates the fw_load_progress value and triggers
        all the callbacks associated.

        Args:
            new_value: New value for the variable.

        """
        self.__fw_load_progress = new_value
        for callback in self.__observers_fw_load_progress:
            callback(new_value)

    def __set_fw_load_errors_enabled(self, new_value: bool) -> None:
        """Updates the fw_load_errors_enabled value and triggers
        all the callbacks associated.

        Args:
            new_value: New value for the variable.

        """
        self.__fw_load_errors_enabled = new_value
        for callback in self.__observers_fw_load_errors_enabled:
            callback(new_value)

    def change_baudrate(
        self,
        target_node: int,
        new_target_baudrate: CAN_BAUDRATE,
        vendor_id: int,
        product_code: int,
        rev_number: int,
        serial_number: int,
    ) -> None:
        """Changes the node ID of a given target node ID.

        .. note::
            The servo must be disconnected after this operation in order
            to make the changes visible and update all the internal data.
            It is also needed a power cycle of the servo otherwise the
            changes will not be applied.

        Args:
            target_node: Node ID of the targeted device.
            new_target_baudrate: New baudrate for the targeted device.
            vendor_id: Vendor ID of the targeted device.
            product_code: Product code of the targeted device.
            rev_number: Revision number of the targeted device.
            serial_number: Serial number of the targeted device.

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
        self,
        target_node: int,
        new_target_node: int,
        vendor_id: int,
        product_code: int,
        rev_number: int,
        serial_number: int,
    ) -> None:
        """Changes the node ID of a given target node ID.

        .. note::
            The servo must be disconnected after this operation in order
            to make the changes visible and update all the internal data.

        Args:
            target_node: Node ID of the targeted device.
            new_target_node: New node ID for the targeted device.
            vendor_id: Vendor ID of the targeted device.
            product_code: Product code of the targeted device.
            rev_number: Revision number of the targeted device.
            serial_number: Serial number of the targeted device.

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

    def _lss_store_configuration(self) -> None:
        """Stores the current configuration of the LSS

        Raises:
            ILError: If the connection was not established yet.
        """
        if self._connection is None:
            raise ILError("Can not store configuration. The connection is not established yet.")
        self._connection.lss.store_configuration()
        sleep(0.1)
        logger.info("Stored new configuration")
        self._connection.lss.send_switch_state_global(self._connection.lss.WAITING_STATE)

    def _lss_reset_connection_nodes(self, target_node: int) -> None:
        """Resets the connection and starts node guarding for the connection nodes.

        Args:
            target_node: Node ID of the targeted device.

        Raises:
            ILError: If the connection was not established yet.

        """
        if self._connection is None:
            raise ILError("Can not reset connection. The connection is not established yet.")
        self._connection.nodes[target_node].nmt.send_command(0x82)

        logger.debug("Wait until node is reset")
        sleep(0.5)

        for servo in self.servos:
            logger.info("Node connected: %i", servo.target)
            node = self._connection.add_node(servo.target)

        # Reset all nodes to default state
        self._connection.lss.send_switch_state_global(self._connection.lss.WAITING_STATE)

        self._connection.nodes[target_node].nmt.start_node_guarding(1)

    def subscribe_to_status(self, node_id: int, callback: Callable[[NET_DEV_EVT], Any]) -> None:  # type: ignore [override]
        """Subscribe to network state changes.

        Args:
            node_id: Drive's node ID.
            callback: Callback function.

        """
        if callback in self.__observers_net_state[node_id]:
            logger.info("Callback already subscribed.")
            return
        self.__observers_net_state[node_id].append(callback)

    def unsubscribe_from_status(self, node_id: int, callback: Callable[[NET_DEV_EVT], Any]) -> None:  # type: ignore [override]
        """Unsubscribe from network state changes.

        Args:
            node_id: Drive's node ID.
            callback: Callback function.

        """
        if callback not in self.__observers_net_state[node_id]:
            logger.info("Callback not subscribed.")
            return
        self.__observers_net_state[node_id].remove(callback)

    def _notify_status(self, node_id: int, status: NET_DEV_EVT) -> None:
        """Notify subscribers of a network state change."""
        for callback in self.__observers_net_state[node_id]:
            callback(status)

    def is_listener_started(self) -> bool:
        return self.__listener_net_status is not None

    def start_status_listener(self) -> None:  # type: ignore [override]
        """Start monitoring network events (CONNECTION/DISCONNECTION)."""
        if self.__listener_net_status is None:
            listener = NetStatusListener(self)
            listener.start()
            self.__listener_net_status = listener

    def stop_status_listener(self) -> None:  # type: ignore [override]
        """Stops the NetStatusListener from listening to the drive."""
        if self._connection is None:
            return
        try:
            for node_id, node_obj in self._connection.nodes.items():
                node_obj.nmt.stop_node_guarding()
        except Exception as e:
            logger.error("Could not stop node guarding. Exception: %s", str(e))
        if self.__listener_net_status is not None:
            self.__listener_net_status.stop()
            self.__listener_net_status.join()
        self.__listener_net_status = None

    @property
    def device(self) -> str:
        """Current device of the network."""
        return self.__device

    @property
    def channel(self) -> Union[int, str]:
        """Current channel of the network."""
        return self.__channel

    @property
    def baudrate(self) -> int:
        """Current baudrate of the network."""
        return self.__baudrate

    @property
    def network(self) -> canopen.Network:
        """Returns the instance of the CANopen Network."""
        return self._connection

    @property
    def protocol(self) -> NET_PROT:
        """Obtain network protocol."""
        return NET_PROT.CAN

    def _get_servo_state(self, node_id: int) -> NET_STATE:
        return self.__servos_state[node_id]

    def _set_servo_state(self, node_id: int, state: NET_STATE) -> None:
        self.__servos_state[node_id] = state
