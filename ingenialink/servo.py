import os
import time
import threading
from enum import Enum
import xml.etree.ElementTree as ET

from ._ingenialink import ffi, lib
from .constants import DEFAULT_DRIVE_NAME
from ingenialink.exceptions import ILIOError, ILRegisterNotFoundError, ILError
from ingenialink.register import Register
from ingenialink.utils._utils import get_drive_identification, cleanup_register

import ingenialogger

logger = ingenialogger.get_logger(__name__)


class SERVO_STATE(Enum):
    """Servo states."""
    NRDY = lib.IL_SERVO_STATE_NRDY
    """Not ready to switch on."""
    DISABLED = lib.IL_SERVO_STATE_DISABLED
    """Switch on disabled."""
    RDY = lib.IL_SERVO_STATE_RDY
    """Ready to be switched on."""
    ON = lib.IL_SERVO_STATE_ON
    """Power switched on."""
    ENABLED = lib.IL_SERVO_STATE_ENABLED
    """Enabled."""
    QSTOP = lib.IL_SERVO_STATE_QSTOP
    """Quick stop."""
    FAULTR = lib.IL_SERVO_STATE_FAULTR
    """Fault reactive."""
    FAULT = lib.IL_SERVO_STATE_FAULT
    """Fault."""


class SERVO_FLAGS(Enum):
    """Status Flags."""
    TGT_REACHED = lib.IL_SERVO_FLAG_TGT_REACHED
    """Target reached."""
    ILIM_ACTIVE = lib.IL_SERVO_FLAG_ILIM_ACTIVE
    """Internal limit active."""
    HOMING_ATT = lib.IL_SERVO_FLAG_HOMING_ATT
    """(Homing) attained."""
    HOMING_ERR = lib.IL_SERVO_FLAG_HOMING_ERR
    """(Homing) error."""
    PV_VZERO = lib.IL_SERVO_FLAG_PV_VZERO
    """(PV) Vocity speed is zero."""
    PP_SPACK = lib.IL_SERVO_FLAG_PP_SPACK
    """(PP) SP acknowledge."""
    IP_ACTIVE = lib.IL_SERVO_FLAG_IP_ACTIVE
    """(IP) active."""
    CS_FOLLOWS = lib.IL_SERVO_FLAG_CS_FOLLOWS
    """(CST/CSV/CSP) follow command value."""
    FERR = lib.IL_SERVO_FLAG_FERR
    """(CST/CSV/CSP/PV) following error."""
    IANGLE_DET = lib.IL_SERVO_FLAG_IANGLE_DET
    """Initial angle determination finished."""


class SERVO_MODE(Enum):
    """Operation Mode."""
    OLV = lib.IL_SERVO_MODE_OLV
    """Open loop (vector mode)."""
    OLS = lib.IL_SERVO_MODE_OLS
    """Open loop (scalar mode)."""
    PP = lib.IL_SERVO_MODE_PP
    """Profile position mode."""
    VEL = lib.IL_SERVO_MODE_VEL
    """Velocity mode."""
    PV = lib.IL_SERVO_MODE_PV
    """Profile velocity mode."""
    PT = lib.IL_SERVO_MODE_PT
    """Profile torque mode."""
    HOMING = lib.IL_SERVO_MODE_HOMING
    """Homing mode."""
    IP = lib.IL_SERVO_MODE_IP
    """Interpolated position mode."""
    CSP = lib.IL_SERVO_MODE_CSP
    """Cyclic sync position mode."""
    CSV = lib.IL_SERVO_MODE_CSV
    """Cyclic sync velocity mode."""
    CST = lib.IL_SERVO_MODE_CST
    """Cyclic sync torque mode."""


class SERVO_UNITS_TORQUE(Enum):
    """Torque Units."""
    NATIVE = lib.IL_UNITS_TORQUE_NATIVE
    """Native"""
    MN = lib.IL_UNITS_TORQUE_MNM
    """Millinewtons*meter."""
    N = lib.IL_UNITS_TORQUE_NM
    """Newtons*meter."""


class SERVO_UNITS_POS(Enum):
    """Position Units."""
    NATIVE = lib.IL_UNITS_POS_NATIVE
    """Native."""
    REV = lib.IL_UNITS_POS_REV
    """Revolutions."""
    RAD = lib.IL_UNITS_POS_RAD
    """Radians."""
    DEG = lib.IL_UNITS_POS_DEG
    """Degrees."""
    UM = lib.IL_UNITS_POS_UM
    """Micrometers."""
    MM = lib.IL_UNITS_POS_MM
    """Millimeters."""
    M = lib.IL_UNITS_POS_M
    """Meters."""


class SERVO_UNITS_VEL(Enum):
    """Velocity Units."""
    NATIVE = lib.IL_UNITS_VEL_NATIVE
    """Native."""
    RPS = lib.IL_UNITS_VEL_RPS
    """Revolutions per second."""
    RPM = lib.IL_UNITS_VEL_RPM
    """Revolutions per minute."""
    RAD_S = lib.IL_UNITS_VEL_RAD_S
    """Radians/second."""
    DEG_S = lib.IL_UNITS_VEL_DEG_S
    """Degrees/second."""
    UM_S = lib.IL_UNITS_VEL_UM_S
    """Micrometers/second."""
    MM_S = lib.IL_UNITS_VEL_MM_S
    """Millimeters/second."""
    M_S = lib.IL_UNITS_VEL_M_S
    """Meters/second."""


class SERVO_UNITS_ACC(Enum):
    """Acceleration Units."""
    NATIVE = lib.IL_UNITS_ACC_NATIVE
    """Native."""
    REV_S2 = lib.IL_UNITS_ACC_REV_S2
    """Revolutions/second^2."""
    RAD_S2 = lib.IL_UNITS_ACC_RAD_S2
    """Radians/second^2."""
    DEG_S2 = lib.IL_UNITS_ACC_DEG_S2
    """Degrees/second^2."""
    UM_S2 = lib.IL_UNITS_ACC_UM_S2
    """Micrometers/second^2."""
    MM_S2 = lib.IL_UNITS_ACC_MM_S2
    """Millimeters/second^2."""
    M_S2 = lib.IL_UNITS_ACC_M_S2
    """Meters/second^2."""


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
        while not self.__stop:
            for subnode in range(1, self.__servo.subnodes):
                try:
                    status_word = self.__servo.read(
                        self.__servo.STATUS_WORD_REGISTERS[subnode], subnode=subnode
                    )
                    state = self.__servo.status_word_decode(status_word)
                    self.__servo._set_state(state, subnode=subnode)
                except ILIOError as e:
                    logger.error("Error getting drive status. "
                                 "Exception : %s", e)
            time.sleep(1.5)

    def stop(self):
        """Stops the loop that reads the status word register"""
        self.__stop = True


class Servo:
    """Declaration of a general Servo object.

    Args:
        target (str, int): Target ID of the servo.
        servo_status_listener (bool): Toggle the listener of the servo for
            its status, errors, faults, etc.

    Raises:
        ILCreationError: If the servo cannot be created.

    """
    def __init__(self, target, servo_status_listener=False):
        self.target = target
        self._info = None
        self.name = DEFAULT_DRIVE_NAME
        prod_name = '' if self.dictionary.part_number is None \
            else self.dictionary.part_number
        self.full_name = f'{prod_name} {self.name} ({self.target})'
        """str: Obtains the servo full name."""
        self.units_torque = None
        """SERVO_UNITS_TORQUE: Torque units."""
        self.units_pos = None
        """SERVO_UNITS_POS: Position units."""
        self.units_vel = None
        """SERVO_UNITS_VEL: Velocity units."""
        self.units_acc = None
        """SERVO_UNITS_ACC: Acceleration units."""
        self.__state = {
            1: lib.IL_SERVO_STATE_NRDY,
            2: lib.IL_SERVO_STATE_NRDY,
            3: lib.IL_SERVO_STATE_NRDY
        }
        self.__observers_servo_state = []
        self.__listener_servo_status = None
        self.__monitoring_num_mapped_registers = 0
        self.__monitoring_channels_size = {}
        self.__monitoring_channels_dtype = {}
        self.__monitoring_data = []
        self.__processed_monitoring_data = []
        self.__disturbance_num_mapped_registers = 0
        self.__disturbance_channels_size = {}
        self.__disturbance_channels_dtype = {}
        self.__disturbance_data_size = 0
        self.__disturbance_data = bytearray()
        if servo_status_listener:
            self.start_status_listener()
        else:
            self.stop_status_listener()

    def start_status_listener(self):
        """Start listening for servo status events (SERVO_STATE)."""
        if self.__listener_servo_status is not None:
            return
        status_word = self.read(self.STATUS_WORD_REGISTERS[1])
        state = self.status_word_decode(status_word)
        self._set_state(state, 1)

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
        if not os.path.isfile(config_file):
            raise FileNotFoundError(f'Could not find {config_file}.')
        if subnode is not None and (not isinstance(subnode, int) or subnode < 0):
            raise ValueError('Invalid subnode')
        with open(config_file, 'r', encoding='utf-8') as xml_file:
            tree = ET.parse(xml_file)
        root = tree.getroot()

        axis = tree.findall('*/Device/Axes/Axis')
        if axis:
            # Multiaxis
            registers = root.findall(
                './Body/Device/Axes/Axis/Registers/Register'
            )
        else:
            # Single axis
            registers = root.findall('./Body/Device/Registers/Register')
        dest_subnodes = [int(element.attrib['subnode']) for element in registers]
        if subnode == 0 and subnode not in dest_subnodes:
            raise ValueError(f'Cannot load {config_file} '
                             f'to subnode {subnode}')
        for element in registers:
            try:
                if 'storage' in element.attrib and element.attrib['access'] == 'rw':
                    if subnode is None:
                        element_subnode = int(element.attrib['subnode'])
                    else:
                        element_subnode = subnode
                    self.write(element.attrib['id'],
                               float(element.attrib['storage']),
                               subnode=element_subnode
                               )
            except ILError as e:
                logger.error("Exception during load_configuration, register "
                             "%s: %s", str(element.attrib['id']), e)

    def save_configuration(self, config_file, subnode=None):
        """Read all dictionary registers content and put it to the dictionary
        storage.

        Args:
            config_file (str): Destination path for the configuration file.
            subnode (int): Subnode of the axis.

        """
        if subnode is not None and (not isinstance(subnode, int) or subnode < 0):
            raise ILError('Invalid subnode')
        prod_code, rev_number = get_drive_identification(self, subnode)

        with open(self._dictionary.path, 'r', encoding='utf-8') as xml_file:
            tree = ET.parse(xml_file)
        root = tree.getroot()

        body = root.find('Body')
        device = root.find('Body/Device')
        categories = root.find('Body/Device/Categories')
        errors = root.find('Body/Errors')

        if 'ProductCode' in device.attrib and prod_code is not None:
            device.attrib['ProductCode'] = str(prod_code)
        if 'RevisionNumber' in device.attrib and rev_number is not None:
            device.attrib['RevisionNumber'] = str(rev_number)

        registers_category = root.find('Body/Device/Registers')
        if registers_category is None:
            # Multiaxis dictionary
            axes_category = root.find('Body/Device/Axes')
            list_axis = root.findall('Body/Device/Axes/Axis')
            self.__update_multiaxis_dict(device, axes_category, list_axis, subnode)
        else:
            # Single axis dictionary
            registers = root.findall('Body/Device/Registers/Register')
            self.__update_single_axis_dict(registers_category, registers, subnode)

        device.remove(categories)
        body.remove(errors)

        image = root.find('./DriveImage')
        if image is not None:
            root.remove(image)

        tree.write(config_file)
        xml_file.close()

    def _get_reg(self, reg, subnode=1):
        """Validates a register.
        Args:
            reg (Register): Targeted register to validate.
            subnode (int): Subnode for the register.
        Returns:
            EthernetRegister: Instance of the desired register from the dictionary.
        Raises:
            ValueError: If the dictionary is not loaded.
            ILWrongRegisterError: If the register has invalid format.
        """
        if isinstance(reg, Register):
            return reg

        elif isinstance(reg, str):
            _dict = self.dictionary
            if not _dict:
                raise ValueError('No dictionary loaded')
            if reg not in _dict.registers(subnode):
                raise ILRegisterNotFoundError(f'Register {reg} not found.')
            return _dict.registers(subnode)[reg]
        else:
            raise TypeError('Invalid register')

    def __update_single_axis_dict(self, registers_category,
                                  registers, subnode):
        """Looks for matches through all the registers' subnodes with the
        given subnode and removes the ones that do not match. It also cleans
        up the registers leaving only paramount information.

        Args:
            registers_category (Element): Registers element containing all registers.
            registers (list): List of registers in the dictionary.
            subnode (int): Subnode to keep in the dictionary.

        Returns:

        """
        for register in registers:
            element_subnode = int(register.attrib['subnode'])
            if subnode in [None, element_subnode]:
                if register.attrib.get('access') == 'rw':
                    self.__update_register_dict(register, element_subnode)
            else:
                registers_category.remove(register)
            cleanup_register(register)

    def __update_multiaxis_dict(self, device, axes_category, list_axis, subnode):
        """Looks for matches through the subnode of each axis and
        removes all the axes that did not match the search. It also
        cleans up all the registers leaving only paramount information.

        Args:
            device (Element): Device element containing all the dictionary info.
            axes_category (Element): Axes element containing all the axis.
            list_axis (list): List of all the axis in the dictionary.
            subnode (int): Subnode to keep in the dictionary.

        """
        for axis in list_axis:
            registers_category = axis.find('./Registers')
            registers = registers_category.findall('./Register')
            if subnode is not None and axis.attrib['subnode'] == str(subnode):
                self.__update_single_axis_dict(registers_category, registers, subnode)
                device.append(registers_category)
                device.remove(axes_category)
                break
            for register in registers:
                element_subnode = int(register.attrib['subnode'])
                if (
                        subnode in [None, element_subnode]
                        and register.attrib.get('access') == 'rw'
                ):
                    self.__update_register_dict(register, element_subnode)
                cleanup_register(register)

    def __update_register_dict(self, register, subnode):
        """Updates the register from a dictionary with the
        storage parameters.

        Args:
            register (Element): Register element to be updated.
            subnode (int): Target subnode.

        Returns:

        """
        try:
            storage = self.read(register.attrib['id'],
                                subnode=subnode)
            register.set('storage', str(storage))

            # Update register object
            reg = self._dictionary.registers(subnode)[register.attrib['id']]
            reg.storage = storage
            reg.storage_valid = 1
        except BaseException as e:
            logger.error("Exception during save_configuration, "
                         "register %s: %s",
                         str(register.attrib['id']), e)

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
