import re
import threading
import time
from abc import abstractmethod
from typing import Any, Callable, Optional, Union
from xml.etree import ElementTree

import ingenialogger
import numpy as np

from ingenialink.bitfield import BitField
from ingenialink.canopen.dictionary import CanopenDictionaryV2, CanopenDictionaryV3
from ingenialink.configuration_file import ConfigRegister, ConfigurationFile
from ingenialink.constants import (
    DEFAULT_DRIVE_NAME,
    DEFAULT_PDS_TIMEOUT,
    MONITORING_BUFFER_SIZE,
    PASSWORD_RESTORE_ALL,
    PASSWORD_STORE_ALL,
    PASSWORD_STORE_RESTORE_SUB_0,
)
from ingenialink.dictionary import (
    CanOpenObject,
    Dictionary,
    DictionaryDescriptor,
    DictionaryError,
    DictionaryV2,
    DictionaryV3,
    Interface,
    SubnodeType,
)
from ingenialink.emcy import EmergencyMessage
from ingenialink.enums.register import RegAccess, RegAddressType, RegDtype
from ingenialink.enums.servo import ServoState
from ingenialink.ethercat.dictionary import EthercatDictionaryV2, EthercatDictionaryV3
from ingenialink.ethernet.dictionary import (
    EoEDictionaryV3,
    EthernetDictionaryV2,
    EthernetDictionaryV3,
)
from ingenialink.exceptions import (
    ILAccessError,
    ILConfigurationError,
    ILDictionaryParseError,
    ILError,
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
    """Dictionary factory.

    Creates the appropriate dictionary instance according to
    the file version and connection interface.
    """

    _VERSION_ABSOLUTE_PATH = "Header/Version"
    _VERSION_REGEX = r"(\d+)\.*(\d*)"
    _MAJOR_VERSION_GROUP = 1
    _MINOR_VERSION_GROUP = 2

    @classmethod
    def create_dictionary(cls, dictionary_path: str, interface: Interface) -> Dictionary:
        """Creates a dictionary instance.

        Choosing the class depending on dictionary version and
        connection interface.

        Args:
            dictionary_path: target dictionary path
            interface: connection interface

        Returns:
            Dictionary instance

        Raises:
            NotImplementedError: Dictionary version is not supported.

        """
        major_version, _ = cls.__get_dictionary_version(dictionary_path)
        if major_version == 3:
            if interface == Interface.CAN:
                return CanopenDictionaryV3(dictionary_path)
            if interface == Interface.ECAT:
                return EthercatDictionaryV3(dictionary_path)
            if interface == Interface.EoE:
                return EoEDictionaryV3(dictionary_path)
            if interface in [Interface.ETH, Interface.VIRTUAL]:
                return EthernetDictionaryV3(dictionary_path)
        if major_version == 2:
            if interface == Interface.CAN:
                return CanopenDictionaryV2(dictionary_path)
            if interface == Interface.ECAT:
                return EthercatDictionaryV2(dictionary_path)
            if interface in [Interface.ETH, Interface.EoE]:
                return EthernetDictionaryV2(dictionary_path)
            if interface == Interface.VIRTUAL:
                return VirtualDictionary(dictionary_path)
        raise NotImplementedError(
            f"Dictionary version {major_version} is not supported for interface {interface.name}"
        )

    @classmethod
    def get_dictionary_description(
        cls, dictionary_path: str, interface: Interface
    ) -> DictionaryDescriptor:
        """Quick function to get target dictionary description.

        Args:
            dictionary_path: target dictionary path
            interface: device interface

        Returns:
            Target dictionary description

        Raises:
            NotImplementedError: Dictionary version is not supported.
        """
        major_version, _ = cls.__get_dictionary_version(dictionary_path)
        if major_version == 3:
            return DictionaryV3.get_description(dictionary_path, interface)
        if major_version == 2:
            return DictionaryV2.get_description(dictionary_path, interface)
        raise NotImplementedError(f"Dictionary version {major_version} is not supported")

    @classmethod
    def __get_dictionary_version(cls, dictionary_path: str) -> tuple[int, int]:
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
            with open(dictionary_path, encoding="utf-8") as xdf_file:
                try:
                    tree = ElementTree.parse(xdf_file)
                except ElementTree.ParseError:
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
        super().__init__()
        self.__servo = servo
        self.__stop = False

    def run(self) -> None:
        """Checks if the drive is alive by reading the status word register."""
        previous_states: dict[int, ServoState] = {}
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
        """Stops the loop that reads the status word register."""
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
    SERIAL_NUMBER_REGISTERS = (
        "DRV_ID_SERIAL_NUMBER_COCO",
        "DRV_ID_SERIAL_NUMBER",
        "FSOE_SERIAL_NUMBER",
    )
    SOFTWARE_VERSION_REGISTERS = (
        "DRV_APP_COCO_VERSION",
        "DRV_ID_SOFTWARE_VERSION",
        "FSOE_SOFTWARE_VERSION",
    )
    PRODUCT_ID_REGISTERS = ("DRV_ID_PRODUCT_CODE_COCO", "DRV_ID_PRODUCT_CODE", "FSOE_PRODUCT_CODE")
    REVISION_NUMBER_REGISTERS = ("DRV_ID_REVISION_NUMBER_COCO", "DRV_ID_REVISION_NUMBER")
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

    __DEFAULT_STORE_RECOVERY_TIMEOUT_S = 4
    __DEFAULT_RESTORE_RECOVERY_TIMEOUT_S = 1.5

    interface: Interface

    def __init__(
        self,
        target: Union[int, str],
        dictionary_path: str,
        servo_status_listener: bool = False,
        disconnect_callback: Optional[Callable[["Servo"], None]] = None,
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
        """ServoUnitsTorque: Torque units."""
        self.units_pos = None
        """ServoUnitsPos: Position units."""
        self.units_vel = None
        """ServoUnitsVel: Velocity units."""
        self.units_acc = None
        """ServoUnitsAcc: Acceleration units."""
        self._lock = threading.Lock()
        self.__observers_servo_state: list[Callable[[ServoState, int], Any]] = []
        self.__listener_servo_status: Optional[ServoStatusListener] = None
        self.__monitoring_data: dict[int, list[Union[int, float]]] = {}
        self.__monitoring_size: dict[int, int] = {}
        self.__monitoring_dtype: dict[int, RegDtype] = {}
        self.__disturbance_data = b""
        self.__disturbance_size: dict[int, int] = {}
        self.__disturbance_dtype: dict[int, str] = {}
        self.__register_update_observers: list[
            Callable[[Servo, Register, Union[int, float, str, bytes]], None]
        ] = []
        if servo_status_listener:
            self.start_status_listener()
        else:
            self.stop_status_listener()
        self._disconnect_callback: Optional[Callable[[Servo], None]] = disconnect_callback

    def start_status_listener(self) -> None:
        """Start listening for servo status events (ServoState)."""
        if self.__listener_servo_status is not None:
            return
        self.__listener_servo_status = ServoStatusListener(self)
        self.__listener_servo_status.start()

    def stop_status_listener(self) -> None:
        """Stop listening for servo status events (ServoState)."""
        if self.__listener_servo_status is None:
            return
        if self.__listener_servo_status.is_alive():
            self.__listener_servo_status.stop()
            self.__listener_servo_status.join()
        self.__listener_servo_status = None

    def is_listener_started(self) -> bool:
        """Check if servo listener is started.

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
            ValueError: If a configuration file from a subnode different from 0
                is attempted to be loaded to subnode 0.
            ValueError: If an invalid subnode is provided.
            ILConfigurationError: If the configuration file differs from the drive state.

        """
        if subnode is not None and (not isinstance(subnode, int) or subnode < 0):
            raise ValueError("Invalid subnode")
        xcf_instance = ConfigurationFile.load_from_xcf(config_file)

        if subnode == 0 and not xcf_instance.contains_node(subnode):
            raise ValueError(f"Cannot check {config_file} at subnode {subnode}")
        registers_errored: list[str] = []
        for register in xcf_instance.registers:
            try:
                stored_data = self.read(register.uid, register.subnode)
            except ILError as e:  # noqa: PERF203
                il_error = f"{register.uid} -- {e}"
                logger.error(
                    "Exception during check_configuration, register %s: %s",
                    register.uid,
                    e,
                )
                registers_errored.append(il_error)
            else:
                compare_conf: Union[int, float, str, bytes, bool, np.float32] = (
                    self._adapt_configuration_file_storage_value(xcf_instance, register)
                )
                compare_drive: Union[int, float, str, bytes, bool, np.float32] = stored_data
                if isinstance(stored_data, float):
                    compare_drive = np.float32(stored_data)
                    compare_conf = np.float32(register.storage)
                if compare_conf != compare_drive:
                    registers_errored.append(
                        f"{register.uid} --- Expected: {compare_conf} | Found: {compare_drive}\n"  # type: ignore[str-bytes-safe]
                    )

        if registers_errored:
            error_message = "Configuration check failed for the following registers:\n"
            for register_error in registers_errored:
                error_message += register_error
            raise ILConfigurationError(error_message)

    def _adapt_configuration_file_storage_value(
        self,
        configuration_file: ConfigurationFile,  # noqa: ARG002
        register: ConfigRegister,
    ) -> Union[int, float, str, bytes]:
        """Adapt storage value to the current servo.

        This function performs no action unless the register is a CanOpen subitem
        that depend on the Node ID, and the XCF file indicates it.

        Args:
            configuration_file: target configuration file
            register: target register

        Returns:
            Adapted storage value
        """
        return register.storage

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
            ValueError: If a configuration file from a subnode different from 0
                is attempted to be loaded to subnode 0.
            ValueError: If an invalid subnode is provided.
            ILError: If strict is set to True and any error occurs during the loading
            configuration process.

        """
        if subnode is not None and (not isinstance(subnode, int) or subnode < 0):
            raise ValueError("Invalid subnode")
        xcf_instance = ConfigurationFile.load_from_xcf(config_file)

        if subnode == 0 and not xcf_instance.contains_node(subnode):
            raise ValueError(f"Cannot load {config_file} to subnode {subnode}")
        for register in xcf_instance.registers:
            try:
                storage = self._adapt_configuration_file_storage_value(xcf_instance, register)
                self.write(
                    register.uid,
                    storage,
                    subnode=register.subnode,
                )
            except ILError as e:  # noqa: PERF203
                exception_message = (
                    f"Exception during load_configuration, register {register.uid}: {e}"
                )
                if strict:
                    raise ILError(exception_message)
                logger.error(exception_message)

    def save_configuration(self, config_file: str, subnode: Optional[int] = None) -> None:
        """Save a drive configuration.

        Read all dictionary registers content and put it to the dictionary
        storage.

        Args:
            config_file: Destination path for the configuration file.
            subnode: Subnode of the axis.

        Raises:
            ILError: if the subnode is invalid.
        """
        if subnode is not None and (not isinstance(subnode, int) or subnode < 0):
            raise ILError("Invalid subnode")

        prod_code = None
        rev_number = None
        firmware_version = None
        drive_info = self.info
        if drive_info["product_code"] is not None:
            prod_code = int(drive_info["product_code"])
        if drive_info["revision_number"] is not None:
            rev_number = int(drive_info["revision_number"])
        if drive_info["firmware_version"] is not None:
            firmware_version = str(drive_info["firmware_version"])
        node_id = None
        if self.interface == Interface.CAN and isinstance(self.target, int):
            node_id = self.target

        xcf_instance = ConfigurationFile.create_empty_configuration(
            self.interface,
            self.dictionary.part_number,
            prod_code,
            rev_number,
            firmware_version,
            node_id,
        )
        for configuration_registers in self._registers_to_save_in_configuration_file(
            subnode
        ).values():
            for configuration_register in configuration_registers:
                try:
                    storage = self.read(configuration_register)
                    if isinstance(storage, bytes):
                        raise NotImplementedError("bytes data not supported")
                    configuration_register.storage = storage
                    configuration_register.storage_valid = True
                    xcf_instance.add_register(configuration_register, storage)
                except (ILError, NotImplementedError) as e:  # noqa: PERF203
                    logger.error(
                        "Exception during save_configuration, register %s: %s",
                        str(configuration_register.identifier),
                        e,
                    )
        xcf_instance.save_to_xcf(config_file)

    def _is_register_valid_for_configuration_file(self, register: Register) -> bool:
        """Check if a register is valid for the configuration file.

        Args:
            register: The register object.

        Returns:
            True if the register can be used for the configuration file. False otherwise.

        """
        return register.access == RegAccess.RW and register.address_type in [
            RegAddressType.NVM_CFG,
            RegAddressType.NVM,
        ]

    def _registers_to_save_in_configuration_file(
        self, subnode: Optional[int]
    ) -> dict[int, list[Register]]:
        """Generate the registers to be used in the configuration file.

        Args:
            subnode: Subnode of the axis.

        Returns:
            A dictionary with a list of valid registers per subnode.

        """
        subnodes = list(self.dictionary.subnodes) if subnode is None else [subnode]
        registers: dict[int, list[Register]] = {subnode: [] for subnode in subnodes}
        for subnode in subnodes:
            registers_dict = self.dictionary.registers(subnode=subnode)
            for register in registers_dict.values():
                if self._is_register_valid_for_configuration_file(register):
                    registers[subnode].append(register)
        return registers

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
        self._wait_for_drive_to_recover(self.__DEFAULT_RESTORE_RECOVERY_TIMEOUT_S)

    def store_parameters(self, subnode: Optional[int] = None) -> None:
        """Store all the current parameters of the target subnode.

        Args:
            subnode: Subnode of the axis. `None` by default which stores
            all the parameters.

        Raises:
            ILError: Invalid subnode.

        """
        r = 0
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
            self.write(reg=self.STORE_MOCO_ALL_REGISTERS, data=PASSWORD_STORE_ALL, subnode=subnode)
            logger.info(f"Store axis {subnode} successfully done.")
        else:
            raise ILError(
                f"The drive's configuration cannot be stored. The subnode value: {subnode} is"
                " invalid."
            )
        self._wait_for_drive_to_recover(self.__DEFAULT_STORE_RECOVERY_TIMEOUT_S)

    def _wait_for_drive_to_recover(self, recovery_time: float) -> None:
        """Wait until the drive recovers from a store/restore operation.

        Args:
            recovery_time: how many seconds to wait for the drive.

        """
        time.sleep(recovery_time)
        # To avoid an error on the first read/write after the drive is
        # recovered, we try to read the status word register.
        # Check issue EVR-906.
        self.is_alive()

    def _get_drive_identification(
        self,
        subnode: Optional[int] = None,
    ) -> tuple[Optional[int], Optional[int]]:
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
            ILStateError: If a subnode cannot be enabled within the timeout.
        """
        # Try fault reset if faulty
        if self.get_state(subnode) in [
            ServoState.FAULT,
            ServoState.FAULTR,
        ]:
            self.fault_reset(subnode=subnode)

        state = self.get_state(subnode)
        while state != ServoState.ENABLED:
            # Check state and command action to reach enabled
            cmd = {
                self.CONTROL_WORD_SWITCH_ON: 1,
                self.CONTROL_WORD_VOLTAGE_ENABLE: 1,
                self.CONTROL_WORD_QUICK_STOP: 1,
                self.CONTROL_WORD_ENABLE_OPERATION: 1,
                self.CONTROL_WORD_FAULT_RESET: 0,
            }
            if state == ServoState.FAULT:
                raise ILStateError(
                    f"The subnode {subnode} could not be enabled within {timeout} ms. "
                    f"The current subnode state is {state}"
                )
            elif state == ServoState.NRDY:
                cmd = {self.CONTROL_WORD_VOLTAGE_ENABLE: 0, self.CONTROL_WORD_FAULT_RESET: 0}
            elif state == ServoState.DISABLED:
                cmd = {
                    self.CONTROL_WORD_SWITCH_ON: 0,
                    self.CONTROL_WORD_VOLTAGE_ENABLE: 1,
                    self.CONTROL_WORD_QUICK_STOP: 1,
                    self.CONTROL_WORD_FAULT_RESET: 0,
                }
            elif state == ServoState.RDY:
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
        """
        state = self.get_state(subnode)
        while state != ServoState.DISABLED:
            if state in [
                ServoState.FAULT,
                ServoState.FAULTR,
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
        """
        state = self.get_state(subnode=subnode)
        if state in [
            ServoState.FAULT,
            ServoState.FAULTR,
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

    def state_wait_change(self, state: ServoState, timeout: int, subnode: int = 1) -> ServoState:
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
            try:
                actual_state = self.get_state(subnode)
            except ILTimeoutError:
                continue

        return actual_state

    def get_state(self, subnode: int = 1) -> ServoState:
        """Get the current drive state.

        Returns:
            current drive state.
        """
        status_word = self.read_bitfields(self.STATUS_WORD_REGISTERS, subnode=subnode)
        state = self.status_word_decode(status_word)
        return state

    def status_word_decode(self, status_word: dict[str, int]) -> ServoState:
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
            state = ServoState.NRDY
        elif not (sw_rtso | sw_so | sw_oe | sw_f) and sw_sod:
            state = ServoState.DISABLED
        elif not (sw_so | sw_oe | sw_f | sw_sod) and (sw_rtso & sw_qs):
            state = ServoState.RDY
        elif not (sw_oe | sw_f | sw_sod) and (sw_rtso & sw_so & sw_qs):
            state = ServoState.ON
        elif not (sw_f | sw_sod) and (sw_rtso & sw_so & sw_oe & sw_qs):
            state = ServoState.ENABLED
        elif not (sw_f | sw_qs | sw_sod) and (sw_rtso & sw_so & sw_oe):
            state = ServoState.QSTOP
        elif not sw_sod and (sw_rtso & sw_so & sw_oe & sw_f):
            state = ServoState.FAULTR
        elif not (sw_rtso | sw_so | sw_oe | sw_sod) and sw_f:
            state = ServoState.FAULT
        else:
            state = ServoState.NRDY
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
        self, channel: int, uid: str, size: int, axis: Optional[int] = None
    ) -> None:
        """Set monitoring mapped register.

        Args:
            channel: Identity channel number.
            uid: Register uid.
            size: Size of data in bytes.
            axis: axis. Should be specified if multiaxis, None otherwise.

        Raises:
            RuntimeError: if the register is not monitoreable.
        """
        register = self.dictionary.get_register(uid, axis=axis)
        if register.monitoring is None:
            raise RuntimeError(f"Register {uid} is not monitoreable.")

        self.__monitoring_data[channel] = []
        self.__monitoring_dtype[channel] = register.dtype
        self.__monitoring_size[channel] = size
        data = self._monitoring_disturbance_data_to_map_register(
            register.monitoring.subnode, register.monitoring.address, register.dtype.value, size
        )
        try:
            self.write(self.__monitoring_map_register(), data=data, subnode=0)
            self.__monitoring_update_num_mapped_registers()
        except ILAccessError:
            self.write(
                self.MONITORING_ADD_REGISTERS_OLD, data=register.monitoring.address, subnode=0
            )

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
        """Get the number of monitoring bytes left to be read.

        Returns:
            number of monitoring bytes left to be read.
        """
        try:
            return int(self.read(self.MONITORING_ACTUAL_NUMBER_BYTES, subnode=0))
        except ILRegisterNotFoundError:
            num_samples = int(self.read(self.MONITORING_ACTUAL_NUMBER_SAMPLES, subnode=0))
            sample_size = sum(self.__monitoring_size[reg] for reg in self.__monitoring_size)
            return num_samples * sample_size

    def monitoring_read_data(self) -> None:
        """Obtain processed monitoring data."""
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
        self,
        channel: int,
    ) -> list[float]:
        """Obtain processed monitoring data of a channel.

        Args:
            channel: Identity channel number.

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
        self.disturbance_data = b""

    def disturbance_set_mapped_register(
        self, channel: int, uid: str, size: int, axis: Optional[int] = None
    ) -> None:
        """Set monitoring mapped register.

        Args:
            channel: Identity channel number.
            uid: Register uid.
            size: Size of data in bytes.
            axis: axis. Should be specified if multiaxis, None otherwise.

        Raises:
            RuntimeError: if the register is not monitoreable.
        """
        register = self.dictionary.get_register(uid, axis=axis)
        if register.monitoring is None:
            raise RuntimeError("Register is not monitoreable.")

        self.__disturbance_size[channel] = size
        self.__disturbance_dtype[channel] = register.dtype.name
        data = self._monitoring_disturbance_data_to_map_register(
            register.monitoring.subnode, register.monitoring.address, register.dtype.value, size
        )
        try:
            self.write(self.__disturbance_map_register(), data=data, subnode=0)
            self.__disturbance_update_num_mapped_registers()
        except ILRegisterNotFoundError:
            self.write(
                self.DISTURBANCE_ADD_REGISTERS_OLD, data=register.monitoring.address, subnode=0
            )

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
        self.__disturbance_data = b""
        self.__disturbance_size = {}
        self.__disturbance_dtype = {}

    def subscribe_to_status(self, callback: Callable[[ServoState, int], Any]) -> None:
        """Subscribe to state changes.

        Args:
            callback: Callback function.
        """
        if callback in self.__observers_servo_state:
            logger.info("Callback already subscribed.")
            return
        self.__observers_servo_state.append(callback)

    def unsubscribe_from_status(self, callback: Callable[[ServoState, int], Any]) -> None:
        """Unsubscribe from state changes.

        Args:
            callback: Callback function.

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
            dictionary: The dictionary path.

        """

    def _get_reg(self, reg: Union[str, Register], subnode: int = 1) -> Register:
        """Validates a register.

        Args:
            reg: Targeted register to validate.
            subnode: Subnode for the register.

        Returns:
            Instance of the desired register from the dictionary.

        Raises:
            ValueError: If the dictionary is not loaded.
            ILRegisterNotFoundError: If the register is not found.
            TypeError: If the register is invalid.
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

    def _notify_state(self, state: ServoState, subnode: int) -> None:
        """Notify the state to the observers.

        Args:
            state: Current servo state.
            subnode: Subnode of the drive.

        """
        for callback in self.__observers_servo_state:
            callback(state, subnode)

    def __read_coco_moco_saco_register(
        self, register_coco: str, register_moco: str, register_saco: Optional[str]
    ) -> str:
        """Read a register from COCO or MOCO.

        If it does not exist, reads the MOCO register.
        If it does not exist, reads the SACO register.

        Args:
            register_coco: COCO Register ID to be read.
            register_moco: MOCO Register ID to be read.
            register_saco: SACO Register ID to be read.
                None if there is no equivalent SACO register.

        Raises:
            ILError: if there is an error reading the register.

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
            if register_saco is None:
                raise ILError(f"Error reading register {register_moco} from MOCO.")
            logger.warning(f"Error reading register {register_moco} from MOCO. Trying SACO")
        try:
            return str(self.read(register_saco, subnode=4))
        except ILError:
            raise ILError(f"Error reading register {register_saco} from SACO.")

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

        Returns:
            arranged data.
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

    def __monitoring_process_data(self, monitoring_data: list[bytes]) -> None:
        """Arrange monitoring data."""
        data_bytes = b""
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
        channels: Union[int, list[int]],
        dtypes: Union[RegDtype, list[RegDtype]],
        data_arr: Union[list[Union[int, float]], list[list[Union[int, float]]]],
        max_size: int,
    ) -> tuple[bytes, list[bytes]]:
        """Divide disturbance data into chunks.

        Args:
            channels: Channel identifier.
            dtypes: Data type.
            data_arr: Data array.
            max_size: Max chunk size in bytes.

        Returns:
            data, chunks.
        """
        if not isinstance(channels, list):
            channels = [channels]
        if not isinstance(dtypes, list):
            dtypes = [dtypes]

        data_arr_aux: list[list[Union[int, float]]]

        if not isinstance(data_arr[0], list):
            num_samples = len(data_arr)
            data_arr_aux = [data_arr]  # type: ignore [list-item]
        else:
            num_samples = len(data_arr[0])
            data_arr_aux = data_arr  # type: ignore [assignment]
        self.write(self.DIST_NUMBER_SAMPLES, num_samples, subnode=0)
        data = b""
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
    ) -> None:
        """Writes a data to a target register.

        Args:
            reg: Target register to be written.
            data: Data to be written.
            subnode: Target axis of the drive.

        Raises:
            ILAccessError: Wrong access to the register.
        """
        _reg = self._get_reg(reg, subnode)

        if _reg.access == RegAccess.RO:
            raise ILAccessError("Register is Read-only")
        data_bytes = data if isinstance(data, bytes) else convert_dtype_to_bytes(data, _reg.dtype)
        self._write_raw(_reg, data_bytes)
        self._notify_register_update(_reg, data)

    def read(
        self,
        reg: Union[str, Register],
        subnode: int = 1,
    ) -> Union[int, float, str, bytes]:
        """Read a register value from servo.

        Args:
            reg: Register.
            subnode: Target axis of the drive.

        Returns:
            int, float or Value stored in the register.

        Raises:
            ILAccessError: Wrong access to the register.
        """
        _reg = self._get_reg(reg, subnode)
        access = _reg.access
        if access == RegAccess.WO:
            raise ILAccessError("Register is Write-only")

        raw_read = self._read_raw(_reg)

        value = convert_bytes_to_dtype(raw_read, _reg.dtype)
        self._notify_register_update(_reg, value)
        return value

    def write_complete_access(
        self, reg: Union[str, Register, CanOpenObject], data: bytes, subnode: int = 1
    ) -> None:
        """Write a complete access register.

        Args:
            reg: Register to be written.
            data: Data to be written.
            subnode: Target subnode of the drive.
        """
        if isinstance(reg, CanOpenObject):
            _reg: Register = reg.registers[0]
        else:
            _reg = self._get_reg(reg, subnode)
        self._write_raw(_reg, data, complete_access=True)

    def read_complete_access(
        self,
        reg: Union[str, Register, CanOpenObject],
        subnode: int = 1,
        buffer_size: Optional[int] = None,
    ) -> bytes:
        """Read a complete access register.

        Args:
            reg: Register to be read.
            subnode: Target subnode of the drive.
            buffer_size: Size of the buffer to read.

        Raises:
            ValueError: if buffer size is not specified or cannot be detected

        Returns:
            Data read from the register.
        """
        if isinstance(reg, CanOpenObject):
            _reg: Register = reg.registers[0]
            buffer_size = reg.byte_length
        else:
            _reg = self._get_reg(reg, subnode)

        if buffer_size is None:
            raise ValueError(
                "Buffer size must be specified for complete access read."
                "Alternatively, use a CanOpenObject to infer the size required "
                "automatically."
            )

        return self._read_raw(_reg, buffer_size=buffer_size, complete_access=True)

    def read_bitfields(
        self,
        reg: Union[str, Register],
        subnode: int = 1,
        bitfields: Optional[dict[str, "BitField"]] = None,
    ) -> dict[str, int]:
        """Read bitfields of a register.

        Args:
            reg: Register.
            subnode: Target subnode of the drive.
            bitfields: Optional bitfield specification.
                If not it will be used from the register definition (if Any).

        Raises:
            ValueError: if the register does not have bitfields.
            TypeError: if the register is not of integer type.

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
        values: dict[str, int],
        subnode: int = 1,
        bitfields: Optional[dict[str, "BitField"]] = None,
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

        Raises:
            ValueError: if the register does not have bitfields.
            TypeError: if the register is not of integer type.
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
        channels: Union[int, list[int]],
        dtypes: Union[RegDtype, list[RegDtype]],
        data_arr: Union[list[Union[int, float]], list[list[Union[int, float]]]],
    ) -> None:
        """Write disturbance data.

        Args:
            channels: Channel identifier.
            dtypes: Data type.
            data_arr: Data array.

        Raises:
            ILValueError: if the disturbance data cannot be written.
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

    def _is_monitoring_implemented(self) -> bool:
        """Checks if monitoring is supported by the device.

        Returns:
            True if monitoring is implemented.

        """
        return not (self.MONITORING_DATA not in self.dictionary.registers(0))

    def _monitoring_read_data(self) -> bytes:
        """Read monitoring data frame.

        Raises:
            NotImplementedError: If monitoring is not supported by the device.
            ValueError: if the data read is not of type bytes.

        Returns:
            monitoring data read.
        """
        if not self._is_monitoring_implemented():
            raise NotImplementedError("Monitoring is not supported by this device.")
        if not isinstance(data := self.read(self.MONITORING_DATA, subnode=0), bytes):
            raise ValueError(
                f"Error reading monitoring data. Expected type bytes, got {type(data)}"
            )
        return data

    def _is_disturbance_implemented(self) -> bool:
        """Checks if disturbance is supported by the device.

        Returns:
            True if disturbance is implemented.

        """
        return not (self.DIST_DATA not in self.dictionary.registers(0))

    def _disturbance_write_data(self, data: bytes) -> None:
        """Write disturbance data.

        Args:
            data: Data to be written.

        Raises:
            NotImplementedError: If disturbance is not supported by the device.

        """
        if not self._is_disturbance_implemented():
            raise NotImplementedError("Disturbance is not supported by this device.")
        return self.write(self.DIST_DATA, subnode=0, data=data)

    @abstractmethod
    def _write_raw(self, reg: Register, data: bytes, **kwargs: Any) -> None:
        """Write raw bytes to a target register.

        Args:
            reg: Target register to be written.
            data: Data to be written.
            **kwargs: Additional arguments for the write operation.

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
    def _read_raw(self, reg: Register, **kwargs: Any) -> bytes:
        """Read raw bytes from a target register.

        Args:
            reg: Register.
            kwargs: Additional arguments for the read operation.

        Returns:
            Raw bytes reading from servo.

        Raises:
            ILIOError: Error reading the register.

        """
        raise NotImplementedError

    @property
    def dictionary(self) -> Dictionary:
        """Returns dictionary object."""
        return self._dictionary

    @dictionary.setter
    def dictionary(self, dictionary: Dictionary) -> None:
        """Sets the dictionary object."""
        self._dictionary = dictionary

    @property
    def full_name(self) -> str:
        """Drive full name."""
        return self.__full_name

    @full_name.setter
    def full_name(self, new_name: str) -> None:
        self.__full_name = new_name

    @property
    def status(self) -> dict[int, ServoState]:
        """Servo status."""
        status = {
            subnode: self.get_state(subnode)
            for subnode in self.subnodes
            if self.subnodes[subnode] == SubnodeType.MOTION
        }
        return status

    @property
    def subnodes(self) -> dict[int, SubnodeType]:
        """Dictionary of subnode ids and their type."""
        return self.dictionary.subnodes

    @property
    def errors(self) -> dict[int, DictionaryError]:
        """Errors."""
        return self.dictionary.errors

    @property
    def info(self) -> dict[str, Union[None, str, int]]:
        """Servo information."""
        try:
            serial_number = self.__read_coco_moco_saco_register(
                self.SERIAL_NUMBER_REGISTERS[0],
                self.SERIAL_NUMBER_REGISTERS[1],
                self.SERIAL_NUMBER_REGISTERS[2],
            )
        except ILError:
            serial_number = None
        try:
            sw_version = self.__read_coco_moco_saco_register(
                self.SOFTWARE_VERSION_REGISTERS[0],
                self.SOFTWARE_VERSION_REGISTERS[1],
                self.SOFTWARE_VERSION_REGISTERS[2],
            )
        except ILError:
            sw_version = None
        try:
            product_code = self.__read_coco_moco_saco_register(
                self.PRODUCT_ID_REGISTERS[0],
                self.PRODUCT_ID_REGISTERS[1],
                self.PRODUCT_ID_REGISTERS[2],
            )
        except ILError:
            product_code = None
        try:
            revision_number = self.__read_coco_moco_saco_register(
                self.REVISION_NUMBER_REGISTERS[0], self.REVISION_NUMBER_REGISTERS[1], None
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
