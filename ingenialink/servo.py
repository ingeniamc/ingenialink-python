import os
import time
import threading
import xml.etree.ElementTree as ET
from xml.dom import minidom
from abc import abstractmethod

from ingenialink.exceptions import (
    ILIOError,
    ILRegisterNotFoundError,
    ILError,
    ILStateError,
    ILAccessError,
    ILTimeoutError,
)
from ingenialink.register import Register
from ingenialink.utils._utils import (
    get_drive_identification,
    convert_bytes_to_dtype,
    convert_dtype_to_bytes,
)
from ingenialink.constants import (
    PASSWORD_RESTORE_ALL,
    PASSWORD_STORE_ALL,
    DEFAULT_PDS_TIMEOUT,
    MONITORING_BUFFER_SIZE,
    DEFAULT_DRIVE_NAME,
)
from ingenialink.utils import constants
from ingenialink.enums.register import REG_DTYPE, REG_ADDRESS_TYPE, REG_ACCESS
from ingenialink.enums.servo import SERVO_STATE

import ingenialogger

logger = ingenialogger.get_logger(__name__)

OPERATION_TIME_OUT = -3


class ServoStatusListener(threading.Thread):
    """Reads the status word to check if the drive is alive.

    Args:
        servo (Servo): Servo instance of the drive.

    """

    def __init__(self, servo):
        super(ServoStatusListener, self).__init__()
        self.__servo = servo
        self.__stop = False

    def run(self):
        """Checks if the drive is alive by reading the status word register"""
        previous_states = {}
        while not self.__stop:
            for subnode in range(1, self.__servo.subnodes):
                try:
                    current_state = self.__servo.get_state(subnode)
                    if subnode not in previous_states or previous_states[subnode] != current_state:
                        previous_states[subnode] = current_state
                        self.__servo._notify_state(current_state, subnode)
                except ILError as e:
                    logger.error("Error getting drive status. Exception : %s", e)
            time.sleep(1.5)

    def stop(self):
        """Stops the loop that reads the status word register"""
        self.__stop = True


class Servo:
    """Declaration of a general Servo object.

    Args:
        target (str, int): Target ID of the servo.
        dictionary_path (str): Path to the dictionary file.
        servo_status_listener (bool): Toggle the listener of the servo for
            its status, errors, faults, etc.

    Raises:
        ILCreationError: If the servo cannot be created.

    """

    DICTIONARY_CLASS = None
    MAX_WRITE_SIZE = None

    STATUS_WORD_REGISTERS = "DRV_STATE_STATUS"
    RESTORE_COCO_ALL = "DRV_RESTORE_COCO_ALL"
    RESTORE_MOCO_ALL_REGISTERS = "DRV_RESTORE_MOCO_ALL"
    STORE_COCO_ALL = "DRV_STORE_COCO_ALL"
    STORE_MOCO_ALL_REGISTERS = "DRV_STORE_MOCO_ALL"
    CONTROL_WORD_REGISTERS = "DRV_STATE_CONTROL"
    SERIAL_NUMBER_REGISTERS = ["DRV_ID_SERIAL_NUMBER_COCO", "DRV_ID_SERIAL_NUMBER"]
    SOFTWARE_VERSION_REGISTERS = ["DRV_APP_COCO_VERSION", "DRV_ID_SOFTWARE_VERSION"]
    PRODUCT_ID_REGISTERS = ["DRV_ID_PRODUCT_CODE_COCO", "DRV_ID_PRODUCT_CODE"]
    REVISION_NUMBER_REGISTERS = ["DRV_ID_REVISION_NUMBER_COCO", "DRV_ID_REVISION_NUMBER"]
    MONITORING_DIST_ENABLE = "MON_DIST_ENABLE"
    MONITORING_REMOVE_DATA = "MON_REMOVE_DATA"
    MONITORING_NUMBER_MAPPED_REGISTERS = "MON_CFG_TOTAL_MAP"
    MONITORING_BYTES_PER_BLOCK = "MON_CFG_BYTES_PER_BLOCK"
    MONITORING_ACTUAL_NUMBER_BYTES = "MON_CFG_BYTES_VALUE"
    MONITORING_DATA = None
    MONITORING_DISTURBANCE_VERSION = "MON_DIST_VERSION"
    DISTURBANCE_ENABLE = "DIST_ENABLE"
    DISTURBANCE_REMOVE_DATA = "DIST_REMOVE_DATA"
    DISTURBANCE_NUMBER_MAPPED_REGISTERS = "DIST_CFG_MAP_REGS"
    DIST_NUMBER_SAMPLES = "DIST_CFG_SAMPLES"
    DIST_DATA = None
    MONITORING_ACTUAL_NUMBER_SAMPLES = "MON_CFG_CYCLES_VALUE"
    DISTURBANCE_REMOVE_REGISTERS_OLD = "DIST_CMD_RM_REGS"
    MONITORING_REMOVE_REGISTERS_OLD = "MON_CMD_RM_REG"
    DISTURBANCE_ADD_REGISTERS_OLD = "DIST_CMD_ADD_REG"
    MONITORING_ADD_REGISTERS_OLD = "MON_OP_ADD_REG"

    def __init__(self, target, dictionary_path=None, servo_status_listener=False):
        self.target = target
        if dictionary_path is not None:
            self._dictionary = self.DICTIONARY_CLASS(dictionary_path)
        else:
            self._dictionary = None
        self._info = None
        self.name = DEFAULT_DRIVE_NAME
        prod_name = "" if self.dictionary.part_number is None else self.dictionary.part_number
        self.full_name = f"{prod_name} {self.name} ({self.target})"
        """str: Obtains the servo full name."""
        self.units_torque = None
        """SERVO_UNITS_TORQUE: Torque units."""
        self.units_pos = None
        """SERVO_UNITS_POS: Position units."""
        self.units_vel = None
        """SERVO_UNITS_VEL: Velocity units."""
        self.units_acc = None
        """SERVO_UNITS_ACC: Acceleration units."""
        self._lock = threading.RLock()
        self.__observers_servo_state = []
        self.__listener_servo_status = None
        self.__monitoring = {}
        self.__disturbance = {"data": bytearray()}
        if servo_status_listener:
            self.start_status_listener()
        else:
            self.stop_status_listener()

    def start_status_listener(self):
        """Start listening for servo status events (SERVO_STATE)."""
        if self.__listener_servo_status is not None:
            return
        self.__listener_servo_status = ServoStatusListener(self)
        self.__listener_servo_status.start()

    def stop_status_listener(self):
        """Stop listening for servo status events (SERVO_STATE)."""
        if self.__listener_servo_status is None:
            return
        if self.__listener_servo_status.is_alive():
            self.__listener_servo_status.stop()
            self.__listener_servo_status.join()
        self.__listener_servo_status = None

    def load_configuration(self, config_file, subnode=None):
        """Write current dictionary storage to the servo drive.

        Args:
            config_file (str): Path to the dictionary.
            subnode (int): Subnode of the axis.

        Raises:
            FileNotFoundError: If the configuration file cannot be found.
            ValueError: If a configuration file from a subnode different from 0
            is attempted to be loaded to subnode 0.
            ValueError: If an invalid subnode is provided.

        """
        if subnode is not None and (not isinstance(subnode, int) or subnode < 0):
            raise ValueError("Invalid subnode")
        _, registers = self._read_configuration_file(config_file)

        dest_subnodes = [int(element.attrib["subnode"]) for element in registers]
        if subnode == 0 and subnode not in dest_subnodes:
            raise ValueError(f"Cannot load {config_file} to subnode {subnode}")
        cast_data = {"float": float, "str": str}
        for element in registers:
            try:
                if "storage" in element.attrib and element.attrib["access"] == "rw":
                    if subnode is None:
                        element_subnode = int(element.attrib["subnode"])
                    else:
                        element_subnode = subnode
                    reg_dtype = element.attrib["dtype"]
                    reg_data = element.attrib["storage"]
                    self.write(
                        element.attrib["id"],
                        cast_data.get(reg_dtype, int)(reg_data),
                        subnode=element_subnode,
                    )
            except ILError as e:
                logger.error(
                    "Exception during load_configuration, register %s: %s",
                    str(element.attrib["id"]),
                    e,
                )

    def save_configuration(self, config_file, subnode=None):
        """Read all dictionary registers content and put it to the dictionary
        storage.

        Args:
            config_file (str): Destination path for the configuration file.
            subnode (int): Subnode of the axis.

        """
        if subnode is not None and (not isinstance(subnode, int) or subnode < 0):
            raise ILError("Invalid subnode")
        prod_code, rev_number = get_drive_identification(self, subnode)

        tree = ET.Element("IngeniaDictionary")
        header = ET.SubElement(tree, "Header")
        version = ET.SubElement(header, "Version")
        version.text = "2"
        default_language = ET.SubElement(header, "DefaultLanguage")
        default_language.text = "en_US"

        body = ET.SubElement(tree, "Body")
        device = ET.SubElement(body, "Device")
        registers = ET.SubElement(device, "Registers")

        device.set("Interface", self.dictionary.interface)
        if self.dictionary.part_number is not None:
            device.set("PartNumber", self.dictionary.part_number)
        device.set("ProductCode", str(prod_code))
        device.set("RevisionNumber", str(rev_number))
        device.set("firmwareVersion", self.dictionary.firmware_version)

        access_ops = {value: key for key, value in self.dictionary.access_xdf_options.items()}
        dtype_ops = {value: key for key, value in self.dictionary.dtype_xdf_options.items()}

        if subnode is None:
            subnodes = range(self.dictionary.subnodes)
        else:
            subnodes = [subnode]

        for subnode in subnodes:
            registers_dict = self.dictionary.registers(subnode=subnode)
            for reg_id, register in registers_dict.items():
                if (register.address_type == REG_ADDRESS_TYPE.NVM_NONE) or (
                    register.access != REG_ACCESS.RW
                ):
                    continue
                register_xml = ET.SubElement(registers, "Register")
                register_xml.set("access", access_ops[register.access])
                register_xml.set("dtype", dtype_ops[register.dtype])
                register_xml.set("id", reg_id)
                self.__update_register_dict(register_xml, subnode)
                register_xml.set("subnode", str(subnode))

        dom = minidom.parseString(ET.tostring(tree, encoding="utf-8"))
        with open(config_file, "wb") as f:
            f.write(dom.toprettyxml(indent="\t").encode())

    @staticmethod
    def _read_configuration_file(config_file):
        """Read a configuration file. Returns the device metadata and the registers list.

        Args:
            config_file (str): Path to the dictionary.

        Returns:
            device:
            list: Register list.

        Raises:
            FileNotFoundError: If the configuration file cannot be found.
        """
        if not os.path.isfile(config_file):
            raise FileNotFoundError(f"Could not find {config_file}.")
        with open(config_file, "r", encoding="utf-8") as xml_file:
            tree = ET.parse(xml_file)
        root = tree.getroot()
        device = root.find("Body/Device")
        axis = tree.findall("*/Device/Axes/Axis")
        if axis:
            # Multiaxis
            registers = root.findall("./Body/Device/Axes/Axis/Registers/Register")
        else:
            # Single axis
            registers = root.findall("./Body/Device/Registers/Register")
        return device, registers

    def restore_parameters(self, subnode=None):
        """Restore all the current parameters of all the slave to default.

        .. note::
            The drive needs a power cycle after this
            in order for the changes to be properly applied.

        Args:
            subnode (int): Subnode of the axis. `None` by default which restores
            all the parameters.

        Raises:
            ILError: Invalid subnode.
            ILObjectNotExist: Failed to write to the registers.

        """
        if subnode is None:
            # Restore all
            self.write(reg=self.RESTORE_COCO_ALL, data=PASSWORD_RESTORE_ALL, subnode=0)
            logger.info("Restore all successfully done.")
        elif subnode == 0:
            # Restore subnode 0
            raise ILError("The current firmware version does not have this feature implemented.")
        elif subnode > 0:
            # Restore axis
            self.write(
                reg=self.RESTORE_MOCO_ALL_REGISTERS, data=PASSWORD_RESTORE_ALL, subnode=subnode
            )
            logger.info(f"Restore subnode {subnode} successfully done.")
        else:
            raise ILError("Invalid subnode {subnode}.")
        time.sleep(1.5)

    def store_parameters(self, subnode=None):
        """Store all the current parameters of the target subnode.

        Args:
            subnode (int): Subnode of the axis. `None` by default which stores
            all the parameters.

        Raises:
            ILError: Invalid subnode.
            ILObjectNotExist: Failed to write to the registers.

        """
        r = 0
        try:
            if subnode is None:
                # Store all
                try:
                    self.write(reg=self.STORE_COCO_ALL, data=PASSWORD_STORE_ALL, subnode=0)
                    logger.info("Store all successfully done.")
                except ILError as e:
                    logger.warning(f"Store all COCO failed. Reason: {e}. Trying MOCO...")
                    r = -1
                if r < 0:
                    for dict_subnode in range(1, self.dictionary.subnodes):
                        self.write(
                            reg=self.STORE_MOCO_ALL_REGISTERS,
                            data=PASSWORD_STORE_ALL,
                            subnode=dict_subnode,
                        )
                        logger.info(f"Store axis {dict_subnode} successfully done.")
            elif subnode == 0:
                # Store subnode 0
                raise ILError(
                    "The current firmware version does not have this feature implemented."
                )
            elif subnode > 0:
                # Store axis
                self.write(
                    reg=self.STORE_MOCO_ALL_REGISTERS, data=PASSWORD_STORE_ALL, subnode=subnode
                )
                logger.info(f"Store axis {subnode} successfully done.")
            else:
                raise ILError("Invalid subnode.")
        finally:
            time.sleep(1.5)

    def enable(self, subnode=1, timeout=DEFAULT_PDS_TIMEOUT):
        """Enable PDS.

         Args:
             subnode (int): Subnode of the drive.
             timeout (int): Timeout in milliseconds.

        Raises:
             ILTimeoutError: The servo could not be enabled due to timeout.
             ILError: Failed to enable PDS.

        """
        # Try fault reset if faulty
        if self.get_state(subnode) in [
            SERVO_STATE.FAULT,
            SERVO_STATE.FAULTR,
        ]:
            self.fault_reset(subnode=subnode)

        while self.get_state(subnode) != SERVO_STATE.ENABLED:
            # Read the current state
            state = self.get_state(subnode)

            # Check state and command action to reach enabled
            cmd = constants.IL_MC_PDS_CMD_EO
            if state == SERVO_STATE.FAULT:
                raise ILStateError(None)
            elif state == SERVO_STATE.NRDY:
                cmd = constants.IL_MC_PDS_CMD_DV
            elif state == SERVO_STATE.DISABLED:
                cmd = constants.IL_MC_PDS_CMD_SD
            elif state == SERVO_STATE.RDY:
                cmd = constants.IL_MC_PDS_CMD_SOEO

            self.write(self.CONTROL_WORD_REGISTERS, cmd, subnode=subnode)

            # Wait for state change
            self.state_wait_change(state, timeout, subnode=subnode)

    def disable(self, subnode=1, timeout=DEFAULT_PDS_TIMEOUT):
        """Disable PDS.

        Args:
            subnode (int): Subnode of the drive.
            timeout (int): Timeout in milliseconds.

        Raises:
            ILTimeoutError: The servo could not be disabled due to timeout.
            ILError: Failed to disable PDS.

        """
        while self.get_state(subnode) != SERVO_STATE.DISABLED:
            state = self.get_state(subnode)

            if state in [
                SERVO_STATE.FAULT,
                SERVO_STATE.FAULTR,
            ]:
                # Try fault reset if faulty
                self.fault_reset(subnode=subnode)
            elif state != SERVO_STATE.DISABLED:
                # Check state and command action to reach disabled
                self.write(self.CONTROL_WORD_REGISTERS, constants.IL_MC_PDS_CMD_DV, subnode=subnode)

                # Wait until state changes
                self.state_wait_change(state, timeout, subnode=subnode)

    def fault_reset(self, subnode=1, timeout=DEFAULT_PDS_TIMEOUT):
        """Executes a fault reset on the drive.

        Args:
            subnode (int): Subnode of the drive.
            timeout (int): Timeout in milliseconds.

        Raises:
            ILTimeoutError: If fault reset spend too much time.
            ILError: Failed to fault reset.

        """
        state = self.get_state(subnode=subnode)
        if state in [
            SERVO_STATE.FAULT,
            SERVO_STATE.FAULTR,
        ]:
            # Check if faulty, if so try to reset (0->1)
            self.write(self.CONTROL_WORD_REGISTERS, 0, subnode=subnode)
            self.write(self.CONTROL_WORD_REGISTERS, constants.IL_MC_CW_FR, subnode=subnode)
            # Wait until status word changes
            self.state_wait_change(state, timeout, subnode=subnode)

    def status_word_wait_change(self, status_word, timeout, subnode=1):
        """Waits for a status word change.

        Args:
            status_word (int): Status word to wait for.
            timeout (int): Maximum value to wait for the change.
            subnode (int): Subnode of the drive.

        Raises:
            ILTimeoutError: If status word does not change in the given time.

        """
        start_time = int(round(time.time() * 1000))
        actual_status_word = self.read(self.STATUS_WORD_REGISTERS, subnode=subnode)

        while actual_status_word == status_word:
            current_time = int(round(time.time() * 1000))
            time_diff = current_time - start_time
            if time_diff > timeout:
                raise ILTimeoutError
            actual_status_word = self.read(self.STATUS_WORD_REGISTERS, subnode=subnode)

    def state_wait_change(self, state, timeout, subnode=1):
        """Waits for a state change.

        Args:
            state (SERVO_STATE): Servo state to wait for.
            timeout (int): Maximum value to wait for the change.
            subnode (int): Subnode of the drive.

        Raises:
            ILTimeoutError: If state does not change in the given time.

        """
        start_time = int(round(time.time() * 1000))
        actual_state = self.get_state(subnode)

        while actual_state == state:
            current_time = int(round(time.time() * 1000))
            time_diff = current_time - start_time
            if time_diff > timeout:
                raise ILTimeoutError
            actual_state = self.get_state(subnode)

    def get_state(self, subnode=1):
        """SERVO_STATE: Current drive state."""
        status_word = self.read(self.STATUS_WORD_REGISTERS, subnode=subnode)
        state = self.status_word_decode(status_word)
        return state

    @staticmethod
    def status_word_decode(status_word):
        """Decodes the status word to a known value.

        Args:
            status_word (int): Read value for the status word.

        Returns:
            SERVO_STATE: Status word value.

        """
        if (status_word & constants.IL_MC_PDS_STA_NRTSO_MSK) == constants.IL_MC_PDS_STA_NRTSO:
            state = SERVO_STATE.NRDY
        elif (status_word & constants.IL_MC_PDS_STA_SOD_MSK) == constants.IL_MC_PDS_STA_SOD:
            state = SERVO_STATE.DISABLED
        elif (status_word & constants.IL_MC_PDS_STA_RTSO_MSK) == constants.IL_MC_PDS_STA_RTSO:
            state = SERVO_STATE.RDY
        elif (status_word & constants.IL_MC_PDS_STA_SO_MSK) == constants.IL_MC_PDS_STA_SO:
            state = SERVO_STATE.ON
        elif (status_word & constants.IL_MC_PDS_STA_OE_MSK) == constants.IL_MC_PDS_STA_OE:
            state = SERVO_STATE.ENABLED
        elif (status_word & constants.IL_MC_PDS_STA_QSA_MSK) == constants.IL_MC_PDS_STA_QSA:
            state = SERVO_STATE.QSTOP
        elif (status_word & constants.IL_MC_PDS_STA_FRA_MSK) == constants.IL_MC_PDS_STA_FRA:
            state = SERVO_STATE.FAULTR
        elif (status_word & constants.IL_MC_PDS_STA_F_MSK) == constants.IL_MC_PDS_STA_F:
            state = SERVO_STATE.FAULT
        else:
            state = SERVO_STATE.NRDY
        return state

    def monitoring_enable(self):
        """Enable monitoring process."""
        self.write(self.MONITORING_DIST_ENABLE, data=1, subnode=0)

    def monitoring_disable(self):
        """Disable monitoring process."""
        self.write(self.MONITORING_DIST_ENABLE, data=0, subnode=0)

    def monitoring_remove_data(self):
        """Remove monitoring data."""
        self.write(self.MONITORING_REMOVE_DATA, data=1, subnode=0)

    def monitoring_set_mapped_register(self, channel, address, subnode, dtype, size):
        """Set monitoring mapped register.

        Args:
            channel (int): Identity channel number.
            address (int): Register address to map.
            subnode (int): Subnode to be targeted.
            dtype (int): Register data type.
            size (int): Size of data in bytes.

        """
        self.__monitoring[channel] = {"size": size, "dtype": REG_DTYPE(dtype), "processed_data": []}
        data = self._monitoring_disturbance_data_to_map_register(subnode, address, dtype, size)
        try:
            self.write(self.__monitoring_map_register(), data=data, subnode=0)
            self.__monitoring_update_num_mapped_registers()
        except ILAccessError:
            self.write(self.MONITORING_ADD_REGISTERS_OLD, data=address, subnode=0)

    def monitoring_get_num_mapped_registers(self):
        """Obtain the number of monitoring mapped registers.

        Returns:
            int: Actual number of mapped registers.

        """
        return self.read(self.MONITORING_NUMBER_MAPPED_REGISTERS, 0)

    def monitoring_get_bytes_per_block(self):
        """Obtain Bytes x Block configured.

        Returns:
            int: Actual number of Bytes x Block configured.

        """
        return self.read(self.MONITORING_BYTES_PER_BLOCK, subnode=0)

    def monitoring_remove_all_mapped_registers(self):
        """Remove all monitoring mapped registers."""
        try:
            self.write(self.MONITORING_NUMBER_MAPPED_REGISTERS, data=0, subnode=0)
        except ILAccessError:
            self.write(self.MONITORING_REMOVE_REGISTERS_OLD, data=1, subnode=0)
        self.__monitoring = {}

    def monitoring_actual_number_bytes(self):
        """Get the number of monitoring bytes left to be read."""
        try:
            return self.read(self.MONITORING_ACTUAL_NUMBER_BYTES, subnode=0)
        except ILRegisterNotFoundError:
            num_samples = self.read(self.MONITORING_ACTUAL_NUMBER_SAMPLES, subnode=0)
            sample_size = sum(self.__monitoring[reg]["size"] for reg in self.__monitoring)
            return num_samples * sample_size

    def monitoring_read_data(self):
        """Obtain processed monitoring data.

        Returns:
            array: Actual processed monitoring data.

        """
        num_available_bytes = self.monitoring_actual_number_bytes()
        monitoring_data = []
        while num_available_bytes > 0:
            if num_available_bytes < MONITORING_BUFFER_SIZE:
                limit = num_available_bytes
            else:
                limit = MONITORING_BUFFER_SIZE
            tmp_data = self._monitoring_read_data()[:limit]
            monitoring_data.append(tmp_data)
            num_available_bytes = self.monitoring_actual_number_bytes()
        self.__monitoring_process_data(monitoring_data)

    def monitoring_channel_data(self, channel, dtype=None):
        """Obtain processed monitoring data of a channel.

        Args:
            channel (int): Identity channel number.
            dtype (REG_DTYPE): Data type of the register to map.

        Note:
            The dtype argument is not necessary for this function, it
            was added to maintain compatibility with IPB's implementation
            of monitoring.

        Returns:
            List: Monitoring data.

        """
        return self.__monitoring[channel]["processed_data"]

    def disturbance_enable(self):
        """Enable disturbance process."""
        self.write(self.DISTURBANCE_ENABLE, data=1, subnode=0)

    def disturbance_disable(self):
        """Disable disturbance process."""
        self.write(self.DISTURBANCE_ENABLE, data=0, subnode=0)

    def disturbance_remove_data(self):
        """Remove disturbance data."""
        self.write(self.DISTURBANCE_REMOVE_DATA, data=1, subnode=0)
        self.disturbance_data = bytearray()

    def disturbance_set_mapped_register(self, channel, address, subnode, dtype, size):
        """Set monitoring mapped register.

        Args:
            channel (int): Identity channel number.
            address (int): Register address to map.
            subnode (int): Subnode to be targeted.
            dtype (int): Register data type.
            size (int): Size of data in bytes.

        """
        self.__disturbance[channel] = {"size": size, "dtype": REG_DTYPE(dtype).name}
        data = self._monitoring_disturbance_data_to_map_register(subnode, address, dtype, size)
        try:
            self.write(self.__disturbance_map_register(), data=data, subnode=0)
            self.__disturbance_update_num_mapped_registers()
        except ILRegisterNotFoundError:
            self.write(self.DISTURBANCE_ADD_REGISTERS_OLD, data=address, subnode=0)

    def disturbance_get_num_mapped_registers(self):
        """Obtain the number of disturbance mapped registers.

        Returns:
            int: Actual number of mapped registers.

        """
        return self.read(self.DISTURBANCE_NUMBER_MAPPED_REGISTERS, 0)

    def disturbance_remove_all_mapped_registers(self):
        """Remove all disturbance mapped registers."""
        try:
            self.write(self.DISTURBANCE_NUMBER_MAPPED_REGISTERS, data=0, subnode=0)
        except ILAccessError:
            self.write(self.DISTURBANCE_REMOVE_REGISTERS_OLD, data=1, subnode=0)
        self.__disturbance = {"data": bytearray()}

    def subscribe_to_status(self, callback):
        """Subscribe to state changes.

        Args:
            callback (function): Callback function.

        Returns:
            int: Assigned slot.

        """
        if callback in self.__observers_servo_state:
            logger.info("Callback already subscribed.")
            return
        self.__observers_servo_state.append(callback)

    def unsubscribe_from_status(self, callback):
        """Unsubscribe from state changes.

        Args:
            callback (function): Callback function.

        """
        if callback not in self.__observers_servo_state:
            logger.info("Callback not subscribed.")
            return
        self.__observers_servo_state.remove(callback)

    def is_alive(self):
        """Checks if the servo responds to a reading a register.

        Returns:
            bool: Return code with the result of the read.

        """
        _is_alive = True
        try:
            self.read(self.STATUS_WORD_REGISTERS)
        except ILError as e:
            _is_alive = False
            logger.error(e)
        return _is_alive

    def reload_errors(self, dictionary):
        """Force to reload all dictionary errors.

        Args:
            dictionary (str): Dictionary.

        """
        pass

    def _get_reg(self, reg, subnode=1):
        """Validates a register.
        Args:
            reg (Register): Targeted register to validate.
            subnode (int): Subnode for the register.
        Returns:
            Register: Instance of the desired register from the dictionary.
        Raises:
            ValueError: If the dictionary is not loaded.
            ILWrongRegisterError: If the register has invalid format.
        """
        if isinstance(reg, Register):
            return reg

        elif isinstance(reg, str):
            _dict = self.dictionary
            if not _dict:
                raise ValueError("No dictionary loaded")
            if reg not in _dict.registers(subnode):
                raise ILRegisterNotFoundError(f"Register {reg} not found.")
            return _dict.registers(subnode)[reg]
        else:
            raise TypeError("Invalid register")

    def __update_register_dict(self, register, subnode):
        """Updates the register from a dictionary with the
        storage parameters.

        Args:
            register (Element): Register element to be updated.
            subnode (int): Target subnode.

        Returns:

        """
        try:
            storage = self.read(register.attrib["id"], subnode=subnode)
            register.set("storage", str(storage))

            # Update register object
            reg = self.dictionary.registers(subnode)[register.attrib["id"]]
            reg.storage = storage
            reg.storage_valid = 1
        except BaseException as e:
            logger.error(
                "Exception during save_configuration, register %s: %s",
                str(register.attrib["id"]),
                e,
            )

    def _notify_state(self, state, subnode):
        """Notify the state to the observers.

        Args:
            state (SERVO_STATE): Current servo state.
            subnode (int): Subnode of the drive.

        """
        for callback in self.__observers_servo_state:
            callback(state, None, subnode)

    def __read_coco_moco_register(self, register_coco, register_moco):
        """Reads the COCO register and if it does not exist,
        reads the MOCO register

        Args:
            register_coco (str): COCO Register ID to be read.
            register_moco (str): MOCO Register ID to be read.

        Returns:
            (int, str): Read value of the register.

        """
        try:
            return self.read(register_coco, subnode=0)
        except ILError:
            logger.warning(f"Error reading register {register_coco} from COCO. Trying MOCO")
        try:
            return self.read(register_moco, subnode=1)
        except ILError:
            raise ILError(f"Error reading register {register_moco} from MOCO.")

    def __monitoring_map_register(self):
        """Get the first available Monitoring Mapped Register slot.

        Returns:
            str: Monitoring Mapped Register ID.

        """
        if self.monitoring_number_mapped_registers < 10:
            register_id = f"MON_CFG_REG{self.monitoring_number_mapped_registers}_MAP"
        else:
            register_id = f"MON_CFG_REFG{self.monitoring_number_mapped_registers}_MAP"
        return register_id

    @staticmethod
    def _monitoring_disturbance_data_to_map_register(subnode, address, dtype, size):
        """Arrange necessary data to map a monitoring/disturbance register.

        Args:
            subnode (int): Subnode to be targeted.
            address (int): Register address to map.
            dtype (int): Register data type.
            size (int): Size of data in bytes.

        """
        data_h = address | subnode << 12
        data_l = dtype << 8 | size
        return (data_h << 16) | data_l

    def __monitoring_update_num_mapped_registers(self):
        """Update the number of mapped monitoring registers."""
        self.write(
            self.MONITORING_NUMBER_MAPPED_REGISTERS,
            data=self.monitoring_number_mapped_registers + 1,
            subnode=0,
        )

    def __monitoring_process_data(self, monitoring_data):
        """Arrange monitoring data."""
        data_bytes = bytearray()
        for i in range(len(monitoring_data)):
            data_bytes += monitoring_data[i]
        bytes_per_block = self.monitoring_get_bytes_per_block()
        number_of_blocks = len(data_bytes) // bytes_per_block
        number_of_channels = self.monitoring_get_num_mapped_registers()
        for channel in range(number_of_channels):
            self.__monitoring[channel]["processed_data"] = []
        for block in range(number_of_blocks):
            block_data = data_bytes[
                block * bytes_per_block : block * bytes_per_block + bytes_per_block
            ]
            for channel in range(number_of_channels):
                channel_data_size = self.__monitoring[channel]["size"]
                val = convert_bytes_to_dtype(
                    block_data[:channel_data_size], self.__monitoring[channel]["dtype"]
                )
                self.__monitoring[channel]["processed_data"].append(val)
                block_data = block_data[channel_data_size:]

    def __disturbance_map_register(self):
        """Get the first available Disturbance Mapped Register slot.

        Returns:
            str: Disturbance Mapped Register ID.

        """
        return f"DIST_CFG_REG{self.disturbance_number_mapped_registers}_MAP"

    def __disturbance_update_num_mapped_registers(self):
        """Update the number of mapped disturbance registers."""
        self.write(
            self.DISTURBANCE_NUMBER_MAPPED_REGISTERS,
            data=self.disturbance_number_mapped_registers + 1,
            subnode=0,
        )

    def _disturbance_create_data_chunks(self, channels, dtypes, data_arr, max_size):
        """Divide disturbance data into chunks.

        Args:
            channels (int or list of int): Channel identifier.
            dtypes (int or list of int): Data type.
            data_arr (list or list of list): Data array.
            max_size (int): Max chunk size in bytes.

        """
        if not isinstance(channels, list):
            channels = [channels]
        if not isinstance(dtypes, list):
            dtypes = [dtypes]
        if not isinstance(data_arr[0], list):
            data_arr = [data_arr]
        num_samples = len(data_arr[0])
        self.write(self.DIST_NUMBER_SAMPLES, num_samples, subnode=0)
        data = bytearray()
        for sample_idx in range(num_samples):
            for channel in range(len(data_arr)):
                val = convert_dtype_to_bytes(data_arr[channel][sample_idx], dtypes[channel])
                data += val
        chunks = [data[i : i + max_size] for i in range(0, len(data), max_size)]
        return data, chunks

    def write(self, reg, data, subnode=1):
        """Writes a data to a target register.

        Args:
            reg (Register, str): Target register to be written.
            data (int, str, float): Data to be written.
            subnode (int): Target axis of the drive.

        Raises:
            ILAccessError: Wrong access to the register.
            ILIOError: Error writing the register.

        """
        _reg = self._get_reg(reg, subnode)

        if _reg.access == REG_ACCESS.RO:
            raise ILAccessError("Register is Read-only")
        value = convert_dtype_to_bytes(data, _reg.dtype)
        self._write_raw(_reg, value)

    def read(self, reg, subnode=1):
        """Read a register value from servo.

        Args:
            reg (str, Register): Register.
            subnode (int): Target axis of the drive.

        Returns:
            int, float or str: Value stored in the register.

        Raises:
            ILAccessError: Wrong access to the register.
            ILIOError: Error reading the register.

        """
        _reg = self._get_reg(reg, subnode)
        access = _reg.access
        if access == REG_ACCESS.WO:
            raise ILAccessError("Register is Write-only")

        raw_read = self._read_raw(_reg)
        value = convert_bytes_to_dtype(raw_read, _reg.dtype)
        return value

    def replace_dictionary(self, dictionary):
        """Deletes and creates a new instance of the dictionary.

        Args:
            dictionary (str): Path to the dictionary.

        """
        self._dictionary = self.DICTIONARY_CLASS(dictionary)

    def disturbance_write_data(self, channels, dtypes, data_arr):
        """Write disturbance data.

        Args:
            channels (int or list of int): Channel identifier.
            dtypes (int or list of int): Data type.
            data_arr (list or list of list): Data array.

        """
        data, chunks = self._disturbance_create_data_chunks(
            channels, dtypes, data_arr, self.MAX_WRITE_SIZE
        )
        for chunk in chunks:
            self._write_raw(self.DIST_DATA, data=chunk)
        self.disturbance_data = data

    def _monitoring_read_data(self):
        """Read monitoring data frame."""
        return self._read_raw(self.MONITORING_DATA)

    @abstractmethod
    def _write_raw(self, reg, data):
        """Write raw bytes to a target register.

        Args:
            reg (Register): Target register to be written.
            data (bytearray): Data to be written.
            subnode (int): Target axis of the drive.

        Raises:
            ILIOError: Error writing the register.

        """
        raise NotImplementedError

    @abstractmethod
    def _read_raw(self, reg):
        """Read raw bytes from a target register.

        Args:
            reg (Register): Register.

        Returns:
            bytearray: Raw bytes reading from servo.

        Raises:
            ILIOError: Error reading the register.

        """
        raise NotImplementedError

    @property
    def dictionary(self):
        """Returns dictionary object"""
        return self._dictionary

    @property
    def full_name(self):
        """str: Drive full name."""
        return self.__full_name

    @full_name.setter
    def full_name(self, new_name):
        self.__full_name = new_name

    @property
    def status(self):
        """dict: Servo status."""
        status = {subnode: self.get_state(subnode) for subnode in range(1, self.subnodes)}
        return status

    @property
    def subnodes(self):
        """int: Number of subnodes."""
        return self.dictionary.subnodes

    @property
    def errors(self):
        """dict: Errors."""
        return self.dictionary.errors.errors

    @property
    def info(self):
        """dict: Servo information."""
        serial_number = self.__read_coco_moco_register(
            self.SERIAL_NUMBER_REGISTERS[0], self.SERIAL_NUMBER_REGISTERS[1]
        )
        sw_version = self.__read_coco_moco_register(
            self.SOFTWARE_VERSION_REGISTERS[0], self.SOFTWARE_VERSION_REGISTERS[1]
        )
        product_code = self.__read_coco_moco_register(
            self.PRODUCT_ID_REGISTERS[0], self.PRODUCT_ID_REGISTERS[1]
        )
        revision_number = self.__read_coco_moco_register(
            self.REVISION_NUMBER_REGISTERS[0], self.REVISION_NUMBER_REGISTERS[1]
        )
        hw_variant = "A"

        return {
            "name": self.name,
            "serial_number": serial_number,
            "firmware_version": sw_version,
            "product_code": product_code,
            "revision_number": revision_number,
            "hw_variant": hw_variant,
        }

    @property
    def monitoring_number_mapped_registers(self):
        """Get the number of mapped monitoring registers."""
        return self.read(self.MONITORING_NUMBER_MAPPED_REGISTERS, subnode=0)

    @property
    def monitoring_data_size(self):
        """Obtain monitoring data size.

        Returns:
            int: Current monitoring data size in bytes.

        """
        number_of_samples = self.read("MON_CFG_WINDOW_SAMP", subnode=0)
        return self.monitoring_get_bytes_per_block() * number_of_samples

    @property
    def disturbance_data(self):
        """Obtain disturbance data.

        Returns:
            array: Current disturbance data.

        """
        return self.__disturbance["data"]

    @disturbance_data.setter
    def disturbance_data(self, value):
        """Set disturbance data.

        Args:
            value (array): Array with the disturbance to send.

        """
        self.__disturbance["data"] = value

    @property
    def disturbance_data_size(self):
        """Obtain disturbance data size.

        Returns:
            int: Current disturbance data size.

        """
        return len(self.__disturbance["data"])

    @property
    def disturbance_number_mapped_registers(self):
        """Get the number of mapped disturbance registers."""
        return self.read(self.DISTURBANCE_NUMBER_MAPPED_REGISTERS, subnode=0)
