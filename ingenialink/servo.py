import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from abc import abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from xml.dom import minidom

import ingenialogger
import numpy as np

from ingenialink.bitfield import BitField
from ingenialink.canopen.dictionary import CanopenDictionaryV2
from ingenialink.constants import (
    DEFAULT_DRIVE_NAME,
    DEFAULT_PDS_TIMEOUT,
    MONITORING_BUFFER_SIZE,
    PASSWORD_RESTORE_ALL,
    PASSWORD_STORE_ALL,
    PASSWORD_STORE_RESTORE_SUB_0,
)
from ingenialink.dictionary import (
    Dictionary,
    DictionaryDescriptor,
    DictionaryError,
    DictionaryV2,
    DictionaryV3,
    Interface,
    SubnodeType,
)
from ingenialink.emcy import EmergencyMessage
from ingenialink.enums.register import REG_ACCESS, REG_ADDRESS_TYPE, REG_DTYPE
from ingenialink.enums.servo import SERVO_STATE
from ingenialink.ethercat.dictionary import EthercatDictionaryV2
from ingenialink.ethernet.dictionary import EthernetDictionaryV2
from ingenialink.exceptions import (
    ILAccessError,
    ILConfigurationError,
    ILDictionaryParseError,
    ILError,
    ILIOError,
    ILRegisterNotFoundError,
    ILStateError,
    ILTimeoutError,
    ILValueError,
)
from ingenialink.register import Register
from ingenialink.utils._utils import convert_bytes_to_dtype, convert_dtype_to_bytes
from ingenialink.virtual.dictionary import VirtualDictionary

logger = ingenialogger.get_logger(__name__)

OPERATION_TIME_OUT = -3


class DictionaryFactory:
    """Dictionary factory, creates the appropriate dictionary instance according to
    the file version and connection interface"""

    _VERSION_ABSOLUTE_PATH = "Header/Version"
    _VERSION_REGEX = r"(\d+)\.*(\d*)"
    _MAJOR_VERSION_GROUP = 1
    _MINOR_VERSION_GROUP = 2

    @classmethod
    def create_dictionary(cls, dictionary_path: str, interface: Interface) -> Dictionary:
        """Creates a dictionary instance choosing the class depending on dictionary version and
         connection interface.

        Args:
            dictionary_path: target dictionary path
            interface: connection interface

        Returns:
            Dictionary instance

        Raises:
            FileNotFoundError: dictionary path does not exist.
            ILDictionaryParseError: xdf is not well-formed.
            ILDictionaryParseError: File is not a xdf.
            NotImplementedError: Dictionary version is not supported.

        """
        major_version, minor_version = cls.__get_dictionary_version(dictionary_path)
        if major_version == 3:
            return DictionaryV3(dictionary_path, interface)
        if major_version == 2:
            if interface == Interface.CAN:
                return CanopenDictionaryV2(dictionary_path)
            if interface == Interface.ECAT:
                return EthercatDictionaryV2(dictionary_path)
            if interface in [Interface.ETH, Interface.EoE]:
                return EthernetDictionaryV2(dictionary_path)
            if interface == Interface.VIRTUAL:
                return VirtualDictionary(dictionary_path)
        raise NotImplementedError(f"Dictionary version {major_version} is not supported")

    @classmethod
    def get_dictionary_description(
        cls, dictionary_path: str, interface: Interface
    ) -> DictionaryDescriptor:
        """Quick function to get target dictionary description

        Args:
            dictionary_path: target dictionary path
            interface: device interface

        Returns:
            Target dictionary description

        Raises:
            FileNotFoundError: dictionary path does not exist.
            ILDictionaryParseError: xdf is not well-formed.
            NotImplementedError: Dictionary version is not supported.
        """
        major_version, minor_version = cls.__get_dictionary_version(dictionary_path)
        if major_version == 3:
            return DictionaryV3.get_description(dictionary_path, interface)
        if major_version == 2:
            return DictionaryV2.get_description(dictionary_path, interface)
        raise NotImplementedError(f"Dictionary version {major_version} is not supported")

    @classmethod
    def __get_dictionary_version(cls, dictionary_path: str) -> Tuple[int, int]:
        """Return dictionary version, major and minor version.

        Args:
            dictionary_path: dictionary path

        Returns:
            Major and minor version

        Raises:
            FileNotFoundError: dictionary path does not exist.
            ILDictionaryParseError: xdf is not well-formed
            ILDictionaryParseError: File is not a xdf

        """
        try:
            with open(dictionary_path, "r", encoding="utf-8") as xdf_file:
                try:
                    tree = ET.parse(xdf_file)
                except ET.ParseError:
                    raise ILDictionaryParseError(f"File is not a xdf: {dictionary_path}")
        except FileNotFoundError:
            raise FileNotFoundError(f"There is not any xdf file in the path: {dictionary_path}")
        version_element = tree.find(cls._VERSION_ABSOLUTE_PATH)
        if version_element is None or version_element.text is None:
            raise ILDictionaryParseError("Version not found")
        version_str = version_element.text.strip()
        version_match = re.match(cls._VERSION_REGEX, version_str)
        if version_match is None:
            raise ILDictionaryParseError("Version has a wrong format")
        major_version = int(version_match.group(cls._MAJOR_VERSION_GROUP))
        if version_match.group(cls._MINOR_VERSION_GROUP):
            minor_version = int(version_match.group(cls._MINOR_VERSION_GROUP))
        else:
            minor_version = 0
        return major_version, minor_version


class ServoStatusListener(threading.Thread):
    """Reads the status word to check if the drive is alive.

    Args:
        servo: Servo instance of the drive.

    """

    def __init__(self, servo: "Servo") -> None:
        super(ServoStatusListener, self).__init__()
        self.__servo = servo
        self.__stop = False

    def run(self) -> None:
        """Checks if the drive is alive by reading the status word register"""
        previous_states: Dict[int, SERVO_STATE] = {}
        while not self.__stop:
            for subnode in self.__servo.subnodes:
                if self.__servo.subnodes[subnode] != SubnodeType.MOTION:
                    continue
                try:
                    current_state = self.__servo.get_state(subnode)
                    if subnode not in previous_states or previous_states[subnode] != current_state:
                        previous_states[subnode] = current_state
                        self.__servo._notify_state(current_state, subnode)
                except ILError as e:
                    logger.error("Error getting drive status. Exception : %s", e)
            time.sleep(1.5)

    def stop(self) -> None:
        """Stops the loop that reads the status word register"""
        self.__stop = True


class Servo:
    """Declaration of a general Servo object.

    Args:
        target: Target ID of the servo.
        dictionary_path: Path to the dictionary file.
        servo_status_listener: Toggle the listener of the servo for
            its status, errors, faults, etc.

    Raises:
        ILDictionaryParseError: If dictionary can not be parsed.

    """

    MAX_WRITE_SIZE = 1

    STATUS_WORD_REGISTERS = "DRV_STATE_STATUS"
    STATUS_WORD_READY_TO_SWITCH_ON = "READY_TO_SWITCH_ON"
    STATUS_WORD_SWITCHED_ON = "SWITCHED_ON"
    STATUS_WORD_OPERATION_ENABLED = "OPERATION_ENABLED"
    STATUS_WORD_FAULT = "FAULT"
    STATUS_WORD_QUICK_STOP = "QUICK_STOP"
    STATUS_WORD_SWITCH_ON_DISABLED = "SWITCH_ON_DISABLED"
    RESTORE_COCO_ALL = "DRV_RESTORE_COCO_ALL"
    RESTORE_MOCO_ALL_REGISTERS = "DRV_RESTORE_MOCO_ALL"
    STORE_COCO_ALL = "DRV_STORE_COCO_ALL"
    STORE_MOCO_ALL_REGISTERS = "DRV_STORE_MOCO_ALL"
    CONTROL_WORD_REGISTERS = "DRV_STATE_CONTROL"
    CONTROL_WORD_SWITCH_ON = "SWITCH_ON"
    CONTROL_WORD_VOLTAGE_ENABLE = "VOLTAGE_ENABLE"
    CONTROL_WORD_QUICK_STOP = "QUICK_STOP"
    CONTROL_WORD_ENABLE_OPERATION = "ENABLE_OPERATION"
    CONTROL_WORD_FAULT_RESET = "FAULT_RESET"
    SERIAL_NUMBER_REGISTERS = ["DRV_ID_SERIAL_NUMBER_COCO", "DRV_ID_SERIAL_NUMBER"]
    SOFTWARE_VERSION_REGISTERS = ["DRV_APP_COCO_VERSION", "DRV_ID_SOFTWARE_VERSION"]
    PRODUCT_ID_REGISTERS = ["DRV_ID_PRODUCT_CODE_COCO", "DRV_ID_PRODUCT_CODE"]
    REVISION_NUMBER_REGISTERS = ["DRV_ID_REVISION_NUMBER_COCO", "DRV_ID_REVISION_NUMBER"]
    MONITORING_DIST_ENABLE = "MON_DIST_ENABLE"
    MONITORING_REMOVE_DATA = "MON_REMOVE_DATA"
    MONITORING_NUMBER_MAPPED_REGISTERS = "MON_CFG_TOTAL_MAP"
    MONITORING_BYTES_PER_BLOCK = "MON_CFG_BYTES_PER_BLOCK"
    MONITORING_ACTUAL_NUMBER_BYTES = "MON_CFG_BYTES_VALUE"
    MONITORING_DATA = "MON_DATA_VALUE"
    MONITORING_DISTURBANCE_VERSION = "MON_DIST_VERSION"
    DISTURBANCE_ENABLE = "DIST_ENABLE"
    DISTURBANCE_REMOVE_DATA = "DIST_REMOVE_DATA"
    DISTURBANCE_NUMBER_MAPPED_REGISTERS = "DIST_CFG_MAP_REGS"
    DIST_NUMBER_SAMPLES = "DIST_CFG_SAMPLES"
    DIST_DATA = "DIST_DATA_VALUE"
    MONITORING_ACTUAL_NUMBER_SAMPLES = "MON_CFG_CYCLES_VALUE"
    DISTURBANCE_REMOVE_REGISTERS_OLD = "DIST_CMD_RM_REGS"
    MONITORING_REMOVE_REGISTERS_OLD = "MON_CMD_RM_REG"
    DISTURBANCE_ADD_REGISTERS_OLD = "DIST_CMD_ADD_REG"
    MONITORING_ADD_REGISTERS_OLD = "MON_OP_ADD_REG"

    DICTIONARY_INTERFACE_ATTR_CAN = "CAN"
    DICTIONARY_INTERFACE_ATTR_ETH = "ETH"

    interface: Interface

    def __init__(
        self,
        target: Union[int, str],
        dictionary_path: str,
        servo_status_listener: bool = False,
    ):
        self._dictionary = DictionaryFactory.create_dictionary(dictionary_path, self.interface)
        self.target = target
        prod_name = ""
        if self.dictionary.part_number is not None:
            prod_name = self.dictionary.part_number
        self._info = None
        self.name = DEFAULT_DRIVE_NAME
        self.full_name = f"{prod_name} {self.name} ({self.target})"
        """Obtains the servo full name."""
        self.units_torque = None
        """SERVO_UNITS_TORQUE: Torque units."""
        self.units_pos = None
        """SERVO_UNITS_POS: Position units."""
        self.units_vel = None
        """SERVO_UNITS_VEL: Velocity units."""
        self.units_acc = None
        """SERVO_UNITS_ACC: Acceleration units."""
        self._lock = threading.Lock()
        self.__observers_servo_state: List[Callable[[SERVO_STATE, int], Any]] = []
        self.__listener_servo_status: Optional[ServoStatusListener] = None
        self.__monitoring_data: Dict[int, List[Union[int, float]]] = {}
        self.__monitoring_size: Dict[int, int] = {}
        self.__monitoring_dtype: Dict[int, REG_DTYPE] = {}
        self.__disturbance_data = bytes()
        self.__disturbance_size: Dict[int, int] = {}
        self.__disturbance_dtype: Dict[int, str] = {}
        self.__register_update_observers: List[
            Callable[["Servo", Register, Union[int, float, str, bytes]], None]
        ] = []
        if servo_status_listener:
            self.start_status_listener()
        else:
            self.stop_status_listener()

    def start_status_listener(self) -> None:
        """Start listening for servo status events (SERVO_STATE)."""
        if self.__listener_servo_status is not None:
            return
        self.__listener_servo_status = ServoStatusListener(self)
        self.__listener_servo_status.start()

    def stop_status_listener(self) -> None:
        """Stop listening for servo status events (SERVO_STATE)."""
        if self.__listener_servo_status is None:
            return
        if self.__listener_servo_status.is_alive():
            self.__listener_servo_status.stop()
            self.__listener_servo_status.join()
        self.__listener_servo_status = None

    def is_listener_started(self) -> bool:
        """Check if servo listener is started

        Returns:
            True if listener is started, else False

        """
        return self.__listener_servo_status is not None

    def check_configuration(self, config_file: str, subnode: Optional[int] = None) -> None:
        """Check if the drive is configured in the same way as the given configuration file.
        Compares the value of each register in the given file with the corresponding value in the
        drive.

        Args:
            config_file: the configuration to check
            subnode: Subnode of the axis. Defaults to None.

        Raises:
            FileNotFoundError: If the configuration file cannot be found.
            ValueError: If a configuration file from a subnode different from 0
                is attempted to be loaded to subnode 0.
            ValueError: If an invalid subnode is provided.
            ILConfigurationError: If the configuration file differs from the drive state.

        """
        if subnode is not None and (not isinstance(subnode, int) or subnode < 0):
            raise ValueError("Invalid subnode")
        _, registers = self._read_configuration_file(config_file)

        dest_subnodes = set(int(element.attrib["subnode"]) for element in registers)
        if subnode == 0 and subnode not in dest_subnodes:
            raise ValueError(f"Cannot check {config_file} at subnode {subnode}")
        cast_data = {"float": np.float32, "str": str}
        registers_errored: List[str] = []
        for element in registers:
            if "storage" in element.attrib:
                if subnode is None:
                    element_subnode = int(element.attrib["subnode"])
                else:
                    element_subnode = subnode
                reg_dtype = element.attrib["dtype"]
                reg_data = element.attrib["storage"]
                reg_id = element.attrib["id"]
                try:
                    stored_data: Union[str, int, float, bytes, np.float32] = self.read(
                        reg_id, element_subnode
                    )
                except ILError as e:
                    reg_id = element.attrib["id"]
                    il_error = f"{reg_id} -- {e}"
                    logger.error(
                        "Exception during check_configuration, register %s: %s",
                        str(reg_id),
                        e,
                    )
                    registers_errored.append(il_error)
                else:
                    if isinstance(stored_data, float):
                        stored_data = np.float32(stored_data)
                    reg_data = cast_data.get(reg_dtype, int)(reg_data)
                    if reg_data != stored_data:
                        registers_errored.append(
                            f"{reg_id} --- Expected: {reg_data} | Found: {stored_data}\n"  # type: ignore
                        )

        if registers_errored:
            error_message = "Configuration check failed for the following registers:\n"
            for register_error in registers_errored:
                error_message += register_error
            raise ILConfigurationError(error_message)

    def load_configuration(
        self, config_file: str, subnode: Optional[int] = None, strict: bool = False
    ) -> None:
        """Write current dictionary storage to the servo drive.

        Args:
            config_file: Path to the dictionary.
            subnode: Subnode of the axis.
            strict: Whether to raise an exception if any error occurs during the loading
            configuration process. If false, all errors will only be ignored.
            `False` by default.

        Raises:
            FileNotFoundError: If the configuration file cannot be found.
            ValueError: If a configuration file from a subnode different from 0
                is attempted to be loaded to subnode 0.
            ValueError: If an invalid subnode is provided.
            ILError: If strict is set to True and any error occurs during the loading
            configuration process.

        """
        if subnode is not None and (not isinstance(subnode, int) or subnode < 0):
            raise ValueError("Invalid subnode")
        _, registers = self._read_configuration_file(config_file)

        dest_subnodes = set(int(element.attrib["subnode"]) for element in registers)
        if subnode == 0 and subnode not in dest_subnodes:
            raise ValueError(f"Cannot load {config_file} to subnode {subnode}")
        cast_data = {"float": float, "str": str}
        writable_registers = [
            reg for reg in registers if "storage" in reg.attrib and reg.attrib["access"] == "rw"
        ]
        for element in writable_registers:
            element_subnode = int(element.attrib["subnode"]) if subnode is None else subnode
            reg_dtype = element.attrib["dtype"]
            reg_data = element.attrib["storage"]
            try:
                self.write(
                    element.attrib["id"],
                    cast_data.get(reg_dtype, int)(reg_data),
                    subnode=element_subnode,
                )
            except ILError as e:
                exception_message = (
                    "Exception during load_configuration, "
                    f"register {str(element.attrib['id'])}: {e}"
                )
                if strict:
                    raise ILError(exception_message)
                logger.error(exception_message)

    def save_configuration(self, config_file: str, subnode: Optional[int] = None) -> None:
        """Read all dictionary registers content and put it to the dictionary
        storage.

        Args:
            config_file: Destination path for the configuration file.
            subnode: Subnode of the axis.

        """
        if subnode is not None and (not isinstance(subnode, int) or subnode < 0):
            raise ILError("Invalid subnode")

        drive_info = self.info
        prod_code = drive_info["product_code"]
        rev_number = drive_info["revision_number"]
        firmware_version = drive_info["firmware_version"]

        tree = ET.Element("IngeniaDictionary")
        header = ET.SubElement(tree, "Header")
        version = ET.SubElement(header, "Version")
        version.text = "2"
        default_language = ET.SubElement(header, "DefaultLanguage")
        default_language.text = "en_US"

        body = ET.SubElement(tree, "Body")
        device = ET.SubElement(body, "Device")
        registers = ET.SubElement(device, "Registers")
        interface = (
            self.DICTIONARY_INTERFACE_ATTR_CAN
            if self.dictionary.interface == Interface.CAN
            else self.DICTIONARY_INTERFACE_ATTR_ETH
        )
        device.set("Interface", interface)
        if self.dictionary.part_number is not None:
            device.set("PartNumber", self.dictionary.part_number)
        if prod_code is not None:
            device.set("ProductCode", str(prod_code))
        if rev_number is not None:
            device.set("RevisionNumber", str(rev_number))
        if isinstance(firmware_version, str):
            device.set("firmwareVersion", firmware_version)

        access_ops = {value: key for key, value in self.dictionary.access_xdf_options.items()}
        dtype_ops = {value: key for key, value in self.dictionary.dtype_xdf_options.items()}
        for node, configuration_registers in self._registers_to_save_in_configuration_file(
            subnode
        ).items():
            for configuration_register in configuration_registers:
                if configuration_register.identifier is None:
                    continue
                register_xml = ET.SubElement(registers, "Register")
                register_xml.set("access", access_ops[configuration_register.access])
                register_xml.set("dtype", dtype_ops[configuration_register.dtype])
                register_xml.set("id", configuration_register.identifier)
                self.__update_register_dict(register_xml, node)
                register_xml.set("subnode", str(node))

        dom = minidom.parseString(ET.tostring(tree, encoding="utf-8"))
        with open(config_file, "wb") as f:
            f.write(dom.toprettyxml(indent="\t").encode())

    def _is_register_valid_for_configuration_file(self, register: Register) -> bool:
        """Check if a register is valid for the configuration file.

        Args:
            register: The register object.

        Returns:
            True if the register can be used for the configuration file. False otherwise.

        """
        if (register.access != REG_ACCESS.RW) or (
            register.address_type == REG_ADDRESS_TYPE.NVM_NONE
        ):
            return False
        return True

    def _registers_to_save_in_configuration_file(
        self, subnode: Optional[int]
    ) -> Dict[int, List[Register]]:
        """Generate the registers to be used in the configuration file.

        Args:
            subnode: Subnode of the axis.

        Returns:
            A dictionary with a list of valid registers per subnode.

        """
        if subnode is None:
            subnodes = list(self.dictionary.subnodes)
        else:
            subnodes = [subnode]
        registers: Dict[int, List[Register]] = {subnode: [] for subnode in subnodes}
        for subnode in subnodes:
            registers_dict = self.dictionary.registers(subnode=subnode)
            for reg_id, register in registers_dict.items():
                if self._is_register_valid_for_configuration_file(register):
                    registers[subnode].append(register)
        return registers

    @staticmethod
    def _read_configuration_file(config_file: str) -> Tuple[ET.Element, List[ET.Element]]:
        """Read a configuration file. Returns the device metadata and the registers list.

        Args:
            config_file: Path to the dictionary.

        Returns:
            device:
            Register list.

        Raises:
            FileNotFoundError: If the configuration file cannot be found.
            ILIOError: If the configuration file does not have device information or registers.
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
        if not isinstance(device, ET.Element):
            raise ILIOError("Configuration file does not have device information")
        if not isinstance(registers, list):
            raise ILIOError("Configuration file does not have register list")
        return device, registers

    def restore_parameters(self, subnode: Optional[int] = None) -> None:
        """Restore all the current parameters of all the slave to default.

        .. note::
            The drive needs a power cycle after this
            in order for the changes to be properly applied.

        Args:
            subnode: Subnode of the axis. `None` by default which restores
                all the parameters.

        Raises:
            ILError: Invalid subnode.

        """
        if subnode is None:
            # Restore all
            self.write(reg=self.RESTORE_COCO_ALL, data=PASSWORD_RESTORE_ALL, subnode=0)
            logger.info("Restore all successfully done.")
        elif subnode == 0:
            # Restore subnode 0
            self.write(reg=self.RESTORE_COCO_ALL, data=PASSWORD_STORE_RESTORE_SUB_0, subnode=0)
        elif subnode > 0:
            # Restore axis
            self.write(
                reg=self.RESTORE_MOCO_ALL_REGISTERS, data=PASSWORD_RESTORE_ALL, subnode=subnode
            )
            logger.info(f"Restore subnode {subnode} successfully done.")
        else:
            raise ILError(
                f"The drive's configuration cannot be restored. The subnode value: {subnode} is"
                " invalid."
            )
        time.sleep(1.5)

    def store_parameters(self, subnode: Optional[int] = None) -> None:
        """Store all the current parameters of the target subnode.

        Args:
            subnode: Subnode of the axis. `None` by default which stores
            all the parameters.

        Raises:
            ILError: Invalid subnode.

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
                    for dict_subnode in self.dictionary.subnodes:
                        if self.dictionary.subnodes[dict_subnode] == SubnodeType.MOTION:
                            self.write(
                                reg=self.STORE_MOCO_ALL_REGISTERS,
                                data=PASSWORD_STORE_ALL,
                                subnode=dict_subnode,
                            )
                            logger.info(f"Store axis {dict_subnode} successfully done.")
            elif subnode == 0:
                # Store subnode 0
                self.write(reg=self.STORE_COCO_ALL, data=PASSWORD_STORE_RESTORE_SUB_0, subnode=0)
            elif subnode > 0:
                # Store axis
                self.write(
                    reg=self.STORE_MOCO_ALL_REGISTERS, data=PASSWORD_STORE_ALL, subnode=subnode
                )
                logger.info(f"Store axis {subnode} successfully done.")
            else:
                raise ILError(
                    f"The drive's configuration cannot be stored. The subnode value: {subnode} is"
                    " invalid."
                )
        finally:
            time.sleep(1.5)

    def _get_drive_identification(
        self,
        subnode: Optional[int] = None,
    ) -> Tuple[Optional[int], Optional[int]]:
        """Gets the identification information of a given subnode.

        Args:
            subnode: subnode to be targeted.

        Returns:
            Product code. None if the corresponding register does not exist.
            Revision number. None if the corresponding register does not exist.
        """
        subnode = 0 if subnode is None else subnode
        reg_index = 0 if subnode == 0 else 1
        try:
            prod_code = int(self.read(self.PRODUCT_ID_REGISTERS[reg_index], subnode=subnode))
        except ILRegisterNotFoundError:
            prod_code = None
        try:
            rev_number = int(self.read(self.REVISION_NUMBER_REGISTERS[reg_index], subnode=subnode))
        except ILRegisterNotFoundError:
            rev_number = None

        return prod_code, rev_number

    def enable(self, subnode: int = 1, timeout: int = DEFAULT_PDS_TIMEOUT) -> None:
        """Enable PDS.

         Args:
             subnode: Subnode of the drive.
             timeout: Timeout in milliseconds.

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

        state = self.get_state(subnode)
        while state != SERVO_STATE.ENABLED:
            # Check state and command action to reach enabled
            cmd = {
                self.CONTROL_WORD_SWITCH_ON: 1,
                self.CONTROL_WORD_VOLTAGE_ENABLE: 1,
                self.CONTROL_WORD_QUICK_STOP: 1,
                self.CONTROL_WORD_ENABLE_OPERATION: 1,
                self.CONTROL_WORD_FAULT_RESET: 0,
            }
            if state == SERVO_STATE.FAULT:
                raise ILStateError(
                    f"The subnode {subnode} could not be enabled within {timeout} ms. "
                    f"The current subnode state is {state}"
                )
            elif state == SERVO_STATE.NRDY:
                cmd = {self.CONTROL_WORD_VOLTAGE_ENABLE: 0, self.CONTROL_WORD_FAULT_RESET: 0}
            elif state == SERVO_STATE.DISABLED:
                cmd = {
                    self.CONTROL_WORD_SWITCH_ON: 0,
                    self.CONTROL_WORD_VOLTAGE_ENABLE: 1,
                    self.CONTROL_WORD_QUICK_STOP: 1,
                    self.CONTROL_WORD_FAULT_RESET: 0,
                }
            elif state == SERVO_STATE.RDY:
                cmd = {
                    self.CONTROL_WORD_SWITCH_ON: 1,
                    self.CONTROL_WORD_VOLTAGE_ENABLE: 1,
                    self.CONTROL_WORD_QUICK_STOP: 1,
                    self.CONTROL_WORD_ENABLE_OPERATION: 1,
                    self.CONTROL_WORD_FAULT_RESET: 0,
                }

            self.write_bitfields(self.CONTROL_WORD_REGISTERS, cmd, subnode=subnode)

            # Wait for state change
            state = self.state_wait_change(state, timeout, subnode=subnode)

    def disable(self, subnode: int = 1, timeout: int = DEFAULT_PDS_TIMEOUT) -> None:
        """Disable PDS.

        Args:
            subnode: Subnode of the drive.
            timeout: Timeout in milliseconds.

        Raises:
            ILTimeoutError: The servo could not be disabled due to timeout.
            ILError: Failed to disable PDS.

        """
        state = self.get_state(subnode)
        while state != SERVO_STATE.DISABLED:
            if state in [
                SERVO_STATE.FAULT,
                SERVO_STATE.FAULTR,
            ]:
                # Try fault reset if faulty
                self.fault_reset(subnode=subnode)
                state = self.get_state(subnode)
            else:
                # Check state and command action to reach disabled
                cmd = {self.CONTROL_WORD_VOLTAGE_ENABLE: 0, self.CONTROL_WORD_FAULT_RESET: 0}
                self.write_bitfields(self.CONTROL_WORD_REGISTERS, cmd, subnode=subnode)

                # Wait until state changes
                state = self.state_wait_change(state, timeout, subnode=subnode)

    def fault_reset(self, subnode: int = 1, timeout: int = DEFAULT_PDS_TIMEOUT) -> None:
        """Executes a fault reset on the drive.

        Args:
            subnode: Subnode of the drive.
            timeout: Timeout in milliseconds.

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
            self.write_bitfields(
                self.CONTROL_WORD_REGISTERS, {self.CONTROL_WORD_FAULT_RESET: 0}, subnode=subnode
            )
            self.write_bitfields(
                self.CONTROL_WORD_REGISTERS, {self.CONTROL_WORD_FAULT_RESET: 1}, subnode=subnode
            )
            # Wait until status word changes
            self.state_wait_change(state, timeout, subnode=subnode)

    def status_word_wait_change(self, status_word: int, timeout: int, subnode: int = 1) -> None:
        """Waits for a status word change.

        Args:
            status_word: Status word to wait for.
            timeout: Maximum value to wait for the change.
            subnode: Subnode of the drive.

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

    def state_wait_change(self, state: SERVO_STATE, timeout: int, subnode: int = 1) -> SERVO_STATE:
        """Waits for a state change.

        Args:
            state: Servo state before calling this function.
            timeout: Maximum value to wait for the change.
            subnode: Subnode of the drive.

        Returns:
            The last read state.

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
            # TODO: Remove this try-except after CAP-924 is solved.
            try:
                actual_state = self.get_state(subnode)
            except ILTimeoutError:
                continue

        return actual_state

    def get_state(self, subnode: int = 1) -> SERVO_STATE:
        """Current drive state."""
        status_word = self.read_bitfields(self.STATUS_WORD_REGISTERS, subnode=subnode)
        state = self.status_word_decode(status_word)
        return state

    def status_word_decode(self, status_word: Dict[str, int]) -> SERVO_STATE:
        """Decodes the status word to a known value.

        Args:
            status_word: Read value for the status word.

        Returns:
            Status word value.

        """
        sw_rtso = status_word[self.STATUS_WORD_READY_TO_SWITCH_ON]
        sw_so = status_word[self.STATUS_WORD_SWITCHED_ON]
        sw_oe = status_word[self.STATUS_WORD_OPERATION_ENABLED]
        sw_f = status_word[self.STATUS_WORD_FAULT]
        sw_qs = status_word[self.STATUS_WORD_QUICK_STOP]
        sw_sod = status_word[self.STATUS_WORD_SWITCH_ON_DISABLED]

        if not (sw_rtso | sw_so | sw_oe | sw_f | sw_sod):
            state = SERVO_STATE.NRDY
        elif not (sw_rtso | sw_so | sw_oe | sw_f) and sw_sod:
            state = SERVO_STATE.DISABLED
        elif not (sw_so | sw_oe | sw_f | sw_sod) and (sw_rtso & sw_qs):
            state = SERVO_STATE.RDY
        elif not (sw_oe | sw_f | sw_sod) and (sw_rtso & sw_so & sw_qs):
            state = SERVO_STATE.ON
        elif not (sw_f | sw_sod) and (sw_rtso & sw_so & sw_oe & sw_qs):
            state = SERVO_STATE.ENABLED
        elif not (sw_f | sw_qs | sw_sod) and (sw_rtso & sw_so & sw_oe):
            state = SERVO_STATE.QSTOP
        elif not sw_sod and (sw_rtso & sw_so & sw_oe & sw_f):
            state = SERVO_STATE.FAULTR
        elif not (sw_rtso | sw_so | sw_oe | sw_sod) and sw_f:
            state = SERVO_STATE.FAULT
        else:
            state = SERVO_STATE.NRDY
        return state

    def monitoring_enable(self) -> None:
        """Enable monitoring process."""
        self.write(self.MONITORING_DIST_ENABLE, data=1, subnode=0)

    def monitoring_disable(self) -> None:
        """Disable monitoring process."""
        self.write(self.MONITORING_DIST_ENABLE, data=0, subnode=0)

    def monitoring_remove_data(self) -> None:
        """Remove monitoring data."""
        self.write(self.MONITORING_REMOVE_DATA, data=1, subnode=0)

    def monitoring_set_mapped_register(
        self, channel: int, address: int, subnode: int, dtype: int, size: int
    ) -> None:
        """Set monitoring mapped register.

        Args:
            channel: Identity channel number.
            address: Register address to map.
            subnode: Subnode to be targeted.
            dtype: Register data type.
            size: Size of data in bytes.

        """
        self.__monitoring_data[channel] = []
        self.__monitoring_dtype[channel] = REG_DTYPE(dtype)
        self.__monitoring_size[channel] = size
        data = self._monitoring_disturbance_data_to_map_register(subnode, address, dtype, size)
        try:
            self.write(self.__monitoring_map_register(), data=data, subnode=0)
            self.__monitoring_update_num_mapped_registers()
        except ILAccessError:
            self.write(self.MONITORING_ADD_REGISTERS_OLD, data=address, subnode=0)

    def monitoring_get_num_mapped_registers(self) -> int:
        """Obtain the number of monitoring mapped registers.

        Returns:
            Actual number of mapped registers.

        """
        return int(self.read(self.MONITORING_NUMBER_MAPPED_REGISTERS, 0))

    def monitoring_get_bytes_per_block(self) -> int:
        """Obtain Bytes x Block configured.

        Returns:
            Actual number of Bytes x Block configured.

        """
        return int(self.read(self.MONITORING_BYTES_PER_BLOCK, subnode=0))

    def monitoring_remove_all_mapped_registers(self) -> None:
        """Remove all monitoring mapped registers."""
        try:
            self.write(self.MONITORING_NUMBER_MAPPED_REGISTERS, data=0, subnode=0)
        except ILAccessError:
            self.write(self.MONITORING_REMOVE_REGISTERS_OLD, data=1, subnode=0)
        self.__monitoring_data = {}
        self.__monitoring_size = {}
        self.__monitoring_dtype = {}

    def monitoring_actual_number_bytes(self) -> int:
        """Get the number of monitoring bytes left to be read."""
        try:
            return int(self.read(self.MONITORING_ACTUAL_NUMBER_BYTES, subnode=0))
        except ILRegisterNotFoundError:
            num_samples = int(self.read(self.MONITORING_ACTUAL_NUMBER_SAMPLES, subnode=0))
            sample_size = sum(self.__monitoring_size[reg] for reg in self.__monitoring_size)
            return num_samples * sample_size

    def monitoring_read_data(self) -> None:
        """Obtain processed monitoring data.

        Returns:
            Actual processed monitoring data.

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

    def monitoring_channel_data(
        self, channel: int, dtype: Optional[REG_DTYPE] = None
    ) -> List[float]:
        """Obtain processed monitoring data of a channel.

        Args:
            channel: Identity channel number.
            dtype: Data type of the register to map.

        Note:
            The dtype argument is not necessary for this function, it
            was added to maintain compatibility with IPB's implementation
            of monitoring.

        Returns:
            Monitoring data.

        """
        return self.__monitoring_data[channel]

    def disturbance_enable(self) -> None:
        """Enable disturbance process."""
        self.write(self.DISTURBANCE_ENABLE, data=1, subnode=0)

    def disturbance_disable(self) -> None:
        """Disable disturbance process."""
        self.write(self.DISTURBANCE_ENABLE, data=0, subnode=0)

    def disturbance_remove_data(self) -> None:
        """Remove disturbance data."""
        self.write(self.DISTURBANCE_REMOVE_DATA, data=1, subnode=0)
        self.disturbance_data = bytes()

    def disturbance_set_mapped_register(
        self, channel: int, address: int, subnode: int, dtype: int, size: int
    ) -> None:
        """Set monitoring mapped register.

        Args:
            channel: Identity channel number.
            address: Register address to map.
            subnode: Subnode to be targeted.
            dtype: Register data type.
            size: Size of data in bytes.

        """
        self.__disturbance_size[channel] = size
        self.__disturbance_dtype[channel] = REG_DTYPE(dtype).name
        data = self._monitoring_disturbance_data_to_map_register(subnode, address, dtype, size)
        try:
            self.write(self.__disturbance_map_register(), data=data, subnode=0)
            self.__disturbance_update_num_mapped_registers()
        except ILRegisterNotFoundError:
            self.write(self.DISTURBANCE_ADD_REGISTERS_OLD, data=address, subnode=0)

    def disturbance_get_num_mapped_registers(self) -> int:
        """Obtain the number of disturbance mapped registers.

        Returns:
            Actual number of mapped registers.

        """
        return int(self.read(self.DISTURBANCE_NUMBER_MAPPED_REGISTERS, 0))

    def disturbance_remove_all_mapped_registers(self) -> None:
        """Remove all disturbance mapped registers."""
        try:
            self.write(self.DISTURBANCE_NUMBER_MAPPED_REGISTERS, data=0, subnode=0)
        except ILAccessError:
            self.write(self.DISTURBANCE_REMOVE_REGISTERS_OLD, data=1, subnode=0)
        self.__disturbance_data = bytes()
        self.__disturbance_size = {}
        self.__disturbance_dtype = {}

    def subscribe_to_status(self, callback: Callable[[SERVO_STATE, int], Any]) -> None:
        """Subscribe to state changes.

        Args:
            callback: Callback function.

        Returns:
            Assigned slot.

        """
        if callback in self.__observers_servo_state:
            logger.info("Callback already subscribed.")
            return
        self.__observers_servo_state.append(callback)

    def unsubscribe_from_status(self, callback: Callable[[SERVO_STATE, int], Any]) -> None:
        """Unsubscribe from state changes.

        Args:
            Callback function.

        """
        if callback not in self.__observers_servo_state:
            logger.info("Callback not subscribed.")
            return
        self.__observers_servo_state.remove(callback)

    def is_alive(self) -> bool:
        """Checks if the servo responds to a reading a register.

        Returns:
            Return code with the result of the read.

        """
        _is_alive = True
        try:
            self.read(self.STATUS_WORD_REGISTERS)
        except ILError as e:
            _is_alive = False
            logger.error(e)
        return _is_alive

    def reload_errors(self, dictionary: str) -> None:
        """Force to reload all dictionary errors.

        Args:
            Dictionary.

        """
        pass

    def _get_reg(self, reg: Union[str, Register], subnode: int = 1) -> Register:
        """Validates a register.
        Args:
            reg: Targeted register to validate.
            subnode: Subnode for the register.
        Returns:
            Instance of the desired register from the dictionary.
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

    def __update_register_dict(self, register: ET.Element, subnode: int) -> None:
        """Updates the register from a dictionary with the
        storage parameters.

        Args:
            register: Register element to be updated.
            subnode: Target subnode.

        Returns:

        """
        try:
            storage: Union[str, int, float, bytes, np.float32] = self.read(
                register.attrib["id"], subnode=subnode
            )
            if isinstance(storage, float):
                storage = np.float32(storage)
            register.set("storage", str(storage))

            # Update register object
            reg = self.dictionary.registers(subnode)[register.attrib["id"]]
            reg.storage = storage
            reg.storage_valid = True
        except BaseException as e:
            logger.error(
                "Exception during save_configuration, register %s: %s",
                str(register.attrib["id"]),
                e,
            )

    def _notify_state(self, state: SERVO_STATE, subnode: int) -> None:
        """Notify the state to the observers.

        Args:
            state: Current servo state.
            subnode: Subnode of the drive.

        """
        for callback in self.__observers_servo_state:
            callback(state, subnode)

    def __read_coco_moco_register(self, register_coco: str, register_moco: str) -> str:
        """Reads the COCO register and if it does not exist,
        reads the MOCO register

        Args:
            register_coco: COCO Register ID to be read.
            register_moco: MOCO Register ID to be read.

        Returns:
            Read value of the register.

        """
        try:
            return str(self.read(register_coco, subnode=0))
        except ILError:
            logger.warning(f"Error reading register {register_coco} from COCO. Trying MOCO")
        try:
            return str(self.read(register_moco, subnode=1))
        except ILError:
            raise ILError(f"Error reading register {register_moco} from MOCO.")

    def __monitoring_map_register(self) -> str:
        """Get the first available Monitoring Mapped Register slot.

        Returns:
            Monitoring Mapped Register ID.

        """
        if self.monitoring_number_mapped_registers < 10:
            register_id = f"MON_CFG_REG{self.monitoring_number_mapped_registers}_MAP"
        else:
            register_id = f"MON_CFG_REFG{self.monitoring_number_mapped_registers}_MAP"
        return register_id

    def _monitoring_disturbance_data_to_map_register(
        self, subnode: int, address: int, dtype: int, size: int
    ) -> int:
        """Arrange necessary data to map a monitoring/disturbance register.

        Args:
            subnode: Subnode to be targeted.
            address: Register address to map.
            dtype: Register data type.
            size: Size of data in bytes.

        """
        data_h = address | subnode << 12
        data_l = dtype << 8 | size
        return (data_h << 16) | data_l

    def __monitoring_update_num_mapped_registers(self) -> None:
        """Update the number of mapped monitoring registers."""
        self.write(
            self.MONITORING_NUMBER_MAPPED_REGISTERS,
            data=self.monitoring_number_mapped_registers + 1,
            subnode=0,
        )

    def __monitoring_process_data(self, monitoring_data: List[bytes]) -> None:
        """Arrange monitoring data."""
        data_bytes = bytes()
        for i in range(len(monitoring_data)):
            data_bytes += monitoring_data[i]
        bytes_per_block = self.monitoring_get_bytes_per_block()
        number_of_blocks = len(data_bytes) // bytes_per_block
        number_of_channels = self.monitoring_get_num_mapped_registers()
        for channel in range(number_of_channels):
            self.__monitoring_data[channel] = []
        for block in range(number_of_blocks):
            block_data = data_bytes[
                block * bytes_per_block : block * bytes_per_block + bytes_per_block
            ]
            for channel in range(number_of_channels):
                channel_data_size = self.__monitoring_size[channel]
                val = convert_bytes_to_dtype(
                    block_data[:channel_data_size], self.__monitoring_dtype[channel]
                )
                if not isinstance(val, (int, float)):
                    continue
                self.__monitoring_data[channel].append(val)
                block_data = block_data[channel_data_size:]

    def __disturbance_map_register(self) -> str:
        """Get the first available Disturbance Mapped Register slot.

        Returns:
            Disturbance Mapped Register ID.

        """
        return f"DIST_CFG_REG{self.disturbance_number_mapped_registers}_MAP"

    def __disturbance_update_num_mapped_registers(self) -> None:
        """Update the number of mapped disturbance registers."""
        self.write(
            self.DISTURBANCE_NUMBER_MAPPED_REGISTERS,
            data=self.disturbance_number_mapped_registers + 1,
            subnode=0,
        )

    def _disturbance_create_data_chunks(
        self,
        channels: Union[int, List[int]],
        dtypes: Union[REG_DTYPE, List[REG_DTYPE]],
        data_arr: Union[List[Union[int, float]], List[List[Union[int, float]]]],
        max_size: int,
    ) -> Tuple[bytes, List[bytes]]:
        """Divide disturbance data into chunks.

        Args:
            channels: Channel identifier.
            dtypes: Data type.
            data_arr: Data array.
            max_size: Max chunk size in bytes.

        """
        if not isinstance(channels, list):
            channels = [channels]
        if not isinstance(dtypes, list):
            dtypes = [dtypes]

        data_arr_aux: List[List[Union[int, float]]]

        if not isinstance(data_arr[0], list):
            num_samples = len(data_arr)
            data_arr_aux = [data_arr]  # type: ignore [list-item]
        else:
            num_samples = len(data_arr[0])
            data_arr_aux = data_arr  # type: ignore [assignment]
        self.write(self.DIST_NUMBER_SAMPLES, num_samples, subnode=0)
        data = bytes()
        for sample_idx in range(num_samples):
            for channel in range(len(data_arr_aux)):
                val = convert_dtype_to_bytes(data_arr_aux[channel][sample_idx], dtypes[channel])
                data += val
        chunks = [data[i : i + max_size] for i in range(0, len(data), max_size)]
        return data, chunks

    def write(
        self,
        reg: Union[str, Register],
        data: Union[int, float, str, bytes],
        subnode: int = 1,
        **kwargs: Any,
    ) -> None:
        """Writes a data to a target register.

        Args:
            reg: Target register to be written.
            data: Data to be written.
            subnode: Target axis of the drive.

        Raises:
            ILAccessError: Wrong access to the register.
            ILIOError: Error writing the register.
            ILTimeoutError: Write timeout.

        """
        _reg = self._get_reg(reg, subnode)

        if _reg.access == REG_ACCESS.RO:
            raise ILAccessError("Register is Read-only")
        if isinstance(data, bytes):
            data_bytes = data
        else:
            data_bytes = convert_dtype_to_bytes(data, _reg.dtype)
        self._write_raw(_reg, data_bytes, **kwargs)
        self._notify_register_update(_reg, data)

    def read(
        self, reg: Union[str, Register], subnode: int = 1, **kwargs: Any
    ) -> Union[int, float, str, bytes]:
        """Read a register value from servo.

        Args:
            reg: Register.
            subnode: Target axis of the drive.

        Returns:
            int, float or Value stored in the register.

        Raises:
            ILAccessError: Wrong access to the register.
            ILIOError: Error reading the register.
            ILTimeoutError: Read timeout.

        """
        _reg = self._get_reg(reg, subnode)
        access = _reg.access
        if access == REG_ACCESS.WO:
            raise ILAccessError("Register is Write-only")

        raw_read = self._read_raw(_reg, **kwargs)
        value = convert_bytes_to_dtype(raw_read, _reg.dtype)
        self._notify_register_update(_reg, value)
        return value

    def read_bitfields(
        self,
        reg: Union[str, Register],
        subnode: int = 1,
        bitfields: Optional[Dict[str, "BitField"]] = None,
    ) -> Dict[str, int]:
        """Read bitfields of a register.

        Args:
            reg: Register.
            subnode: Target subnode of the drive.
            bitfields: Optional bitfield specification.
                If not it will be used from the register definition (if Any)

        Returns:
            Dictionary with values of the bitfields.
            Key is the name of the bitfield.
            Value is the value parsed.
        """
        _reg = self._get_reg(reg, subnode)

        if bitfields is None:
            if _reg.bitfields is None:
                raise ValueError(f"Register {_reg.identifier} does not have bitfields")
            bitfields = _reg.bitfields
        value = self.read(_reg, subnode)
        if not isinstance(value, int):
            raise TypeError("Bitfield only work with integer registers")
        return BitField.parse_bitfields(bitfields, value)

    def write_bitfields(
        self,
        reg: Union[str, Register],
        values: Dict[str, int],
        subnode: int = 1,
        bitfields: Optional[Dict[str, "BitField"]] = None,
    ) -> None:
        """Write bitfields of a register.

        Only the values specified will be updated.
        The register will be read first to prevent overwriting other bits.

        Args:
            reg: Register
            values: Dictionary with values of the bitfields.
                Key is the name of the bitfield.
                Value is the value to set.
            subnode: Target subnode of the drive.
            bitfields: Optional bitfield specification.
                If not it will be used from the register definition (if Any)
        """
        _reg = self._get_reg(reg, subnode)
        if bitfields is None:
            if _reg.bitfields is None:
                raise ValueError(f"Register {_reg.identifier} does not have bitfields")
            bitfields = _reg.bitfields

        previous_value = self.read(_reg, subnode)
        if not isinstance(previous_value, int):
            raise TypeError("Bitfield only work with integer registers")

        new_value = BitField.set_bitfields(bitfields, values, previous_value)
        self.write(_reg, new_value, subnode)

    def register_update_subscribe(
        self, callback: Callable[["Servo", Register, Union[int, float, str, bytes]], None]
    ) -> None:
        """Subscribe to register updates.
        The callback will be called when a read/write operation occurs.

        Args:
            callback: Callable that takes a Servo and a Register instance as arguments.

        """
        self.__register_update_observers.append(callback)

    def register_update_unsubscribe(
        self, callback: Callable[["Servo", Register, Union[int, float, str, bytes]], None]
    ) -> None:
        """Unsubscribe to register updates.

        Args:
            callback: Subscribed callback.

        """
        self.__register_update_observers.remove(callback)

    def _notify_register_update(self, reg: Register, data: Union[int, float, str, bytes]) -> None:
        """Notify a register update to the observers.
        The updated value is stored in the register's storage attribute.

        Args:
            reg: Updated register.
            data: Updated value.

        """
        for callback in self.__register_update_observers:
            callback(
                self,
                reg,
                data,
            )

    def replace_dictionary(self, dictionary: str) -> None:
        """Deletes and creates a new instance of the dictionary.

        Args:
            dictionary: Path to the dictionary.

        """
        self._dictionary = DictionaryFactory.create_dictionary(dictionary, self.interface)

    def disturbance_write_data(
        self,
        channels: Union[int, List[int]],
        dtypes: Union[REG_DTYPE, List[REG_DTYPE]],
        data_arr: Union[List[Union[int, float]], List[List[Union[int, float]]]],
    ) -> None:
        """Write disturbance data.

        Args:
            channels: Channel identifier.
            dtypes: Data type.
            data_arr: Data array.

        """
        try:
            data, chunks = self._disturbance_create_data_chunks(
                channels, dtypes, data_arr, self.MAX_WRITE_SIZE
            )
        except OverflowError as e:
            raise ILValueError("Disturbance data cannot be written.") from e
        for chunk in chunks:
            self._disturbance_write_data(chunk)
        self.disturbance_data = data

    def _monitoring_read_data(self, **kwargs: Any) -> bytes:
        """Read monitoring data frame.

        Raises:
            NotImplementedError: If monitoring is not supported by the device.

        """
        if self.MONITORING_DATA not in self.dictionary.registers(0):
            raise NotImplementedError("Monitoring is not supported by this device.")
        if not isinstance(data := self.read(self.MONITORING_DATA, subnode=0, **kwargs), bytes):
            raise ValueError(
                f"Error reading monitoring data. Expected type bytes, got {type(data)}"
            )
        return data

    def _disturbance_write_data(self, data: bytes, **kwargs: Any) -> None:
        """Write disturbance data.

        Raises:
            NotImplementedError: If disturbance is not supported by the device.

        """
        if self.DIST_DATA not in self.dictionary.registers(0):
            raise NotImplementedError("Disturbance is not supported by this device.")
        return self.write(self.DIST_DATA, subnode=0, data=data, **kwargs)

    @abstractmethod
    def _write_raw(self, reg: Register, data: bytes) -> None:
        """Write raw bytes to a target register.

        Args:
            reg: Target register to be written.
            data: Data to be written.

        Raises:
            ILIOError: Error writing the register.

        """
        raise NotImplementedError

    def emcy_subscribe(self, callback: Callable[[EmergencyMessage], None]) -> None:
        """Subscribe to emergency messages.

        Args:
            callback: Callable that takes an EmergencyMessage instance as argument.

        """
        raise NotImplementedError

    def emcy_unsubscribe(self, callback: Callable[[EmergencyMessage], None]) -> None:
        """Unsubscribe from emergency messages.

        Args:
            callback: Subscribed callback.

        """
        raise NotImplementedError

    @abstractmethod
    def _read_raw(self, reg: Register) -> bytes:
        """Read raw bytes from a target register.

        Args:
            reg: Register.

        Returns:
            Raw bytes reading from servo.

        Raises:
            ILIOError: Error reading the register.

        """
        raise NotImplementedError

    @property
    def dictionary(self) -> Dictionary:
        """Returns dictionary object"""
        return self._dictionary

    @dictionary.setter
    def dictionary(self, dictionary: Dictionary) -> None:
        """Sets the dictionary object"""
        self._dictionary = dictionary

    @property
    def full_name(self) -> str:
        """Drive full name."""
        return self.__full_name

    @full_name.setter
    def full_name(self, new_name: str) -> None:
        self.__full_name = new_name

    @property
    def status(self) -> Dict[int, SERVO_STATE]:
        """Servo status."""
        status = {
            subnode: self.get_state(subnode)
            for subnode in self.subnodes
            if self.subnodes[subnode] == SubnodeType.MOTION
        }
        return status

    @property
    def subnodes(self) -> Dict[int, SubnodeType]:
        """Dictionary of subnode ids and their type"""
        return self.dictionary.subnodes

    @property
    def errors(self) -> Dict[int, DictionaryError]:
        """Errors."""
        return self.dictionary.errors

    @property
    def info(self) -> Dict[str, Union[None, str, int]]:
        """Servo information."""
        try:
            serial_number = self.__read_coco_moco_register(
                self.SERIAL_NUMBER_REGISTERS[0], self.SERIAL_NUMBER_REGISTERS[1]
            )
        except ILError:
            serial_number = None
        try:
            sw_version = self.__read_coco_moco_register(
                self.SOFTWARE_VERSION_REGISTERS[0], self.SOFTWARE_VERSION_REGISTERS[1]
            )
        except ILError:
            sw_version = None
        try:
            product_code = self.__read_coco_moco_register(
                self.PRODUCT_ID_REGISTERS[0], self.PRODUCT_ID_REGISTERS[1]
            )
        except ILError:
            product_code = None
        try:
            revision_number = self.__read_coco_moco_register(
                self.REVISION_NUMBER_REGISTERS[0], self.REVISION_NUMBER_REGISTERS[1]
            )
        except ILError:
            revision_number = None
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
    def monitoring_number_mapped_registers(self) -> int:
        """Get the number of mapped monitoring registers."""
        return int(self.read(self.MONITORING_NUMBER_MAPPED_REGISTERS, subnode=0))

    @property
    def monitoring_data_size(self) -> int:
        """Obtain monitoring data size.

        Returns:
            Current monitoring data size in bytes.

        """
        number_of_samples = int(self.read("MON_CFG_WINDOW_SAMP", subnode=0))
        return self.monitoring_get_bytes_per_block() * number_of_samples

    @property
    def disturbance_data(self) -> bytes:
        """Obtain disturbance data.

        Returns:
            Current disturbance data.

        """
        return self.__disturbance_data

    @disturbance_data.setter
    def disturbance_data(self, value: bytes) -> None:
        """Set disturbance data.

        Args:
            value: Array with the disturbance to send.

        """
        self.__disturbance_data = value

    @property
    def disturbance_data_size(self) -> int:
        """Obtain disturbance data size.

        Returns:
            Current disturbance data size.

        """
        return len(self.__disturbance_data)

    @property
    def disturbance_number_mapped_registers(self) -> int:
        """Get the number of mapped disturbance registers."""
        return int(self.read(self.DISTURBANCE_NUMBER_MAPPED_REGISTERS, subnode=0))
