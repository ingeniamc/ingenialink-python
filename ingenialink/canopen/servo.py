import os
import time
import threading
import canopen
from canopen.emcy import EmcyConsumer
import struct
import xml.etree.ElementTree as ET

from .constants import *
from ..constants import *
from ..exceptions import *
from .._ingenialink import lib
from ingenialink.utils._utils import *
from ..servo import SERVO_STATE, Servo
from .dictionary import CanopenDictionary
from .register import CanopenRegister, REG_DTYPE, REG_ACCESS
from ingenialink.register_deprecated import dtype_size

import ingenialogger
logger = ingenialogger.get_logger(__name__)

CANOPEN_SDO_RESPONSE_TIMEOUT = 0.3

PRODUCT_ID_REGISTERS = {
    0: CanopenRegister(
        identifier='', units='', subnode=0, idx=0x5EE1, subidx=0x00,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
    ),
    1: CanopenRegister(
        identifier='', units='', subnode=1, idx=0x26E1, subidx=0x00,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
    )
}

SERIAL_NUMBER_REGISTERS = {
    0: CanopenRegister(
        identifier='', units='', subnode=0, idx=0x5EE6, subidx=0x00,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
    ),
    1: CanopenRegister(
        identifier='', units='', subnode=1, idx=0x26E6, subidx=0x00,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
    )
}

SOFTWARE_VERSION_REGISTERS = {
    0: CanopenRegister(
        identifier='', units='', subnode=0, idx=0x5EE4, subidx=0x00,
        cyclic='CONFIG', dtype=REG_DTYPE.STR, access=REG_ACCESS.RO
    ),
    1: CanopenRegister(
        identifier='', units='', subnode=1, idx=0x26E4, subidx=0x00,
        cyclic='CONFIG', dtype=REG_DTYPE.STR, access=REG_ACCESS.RO
    )
}

REVISION_NUMBER_REGISTERS = {
    0: CanopenRegister(
        identifier='', units='', subnode=0, idx=0x5EE2, subidx=0x00,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
    ),
    1: CanopenRegister(
        identifier='', units='', subnode=1, idx=0x26E2, subidx=0x00,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
    )
}

STATUS_WORD_REGISTERS = {
    1: CanopenRegister(
        identifier='', units='', subnode=1, idx=0x6041, subidx=0x00,
        cyclic='CYCLIC_TX', dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
    ),
    2: CanopenRegister(
        identifier='', units='', subnode=2, idx=0x6841, subidx=0x00,
        cyclic='CYCLIC_TX', dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
    ),
    3: CanopenRegister(
        identifier='', units='', subnode=3, idx=0x7041, subidx=0x00,
        cyclic='CYCLIC_TX', dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
    )
}

CONTROL_WORD_REGISTERS = {
    1: CanopenRegister(
        identifier='', units='', subnode=1, idx=0x2010, subidx=0x00,
        cyclic='CYCLIC_RX', dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
    ),
    2: CanopenRegister(
        identifier='', units='', subnode=2, idx=0x2810, subidx=0x00,
        cyclic='CYCLIC_RX', dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
    ),
    3: CanopenRegister(
        identifier='', units='', subnode=3, idx=0x3010, subidx=0x00,
        cyclic='CYCLIC_RX', dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
    )
}

STORE_COCO_ALL = CanopenRegister(
    identifier='', units='', subnode=0, idx=0x1010, subidx=0x01, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
)

RESTORE_COCO_ALL = CanopenRegister(
    identifier='', units='', subnode=0, idx=0x1011, subidx=0x01, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
)

STORE_MOCO_ALL_REGISTERS = {
    1: CanopenRegister(
        identifier='', units='', subnode=1, idx=0x26DB, subidx=0x00,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    ),
    2: CanopenRegister(
        identifier='', units='', subnode=2, idx=0x2EDB, subidx=0x00,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    ),
    3: CanopenRegister(
        identifier='', units='', subnode=3, idx=0x36DB, subidx=0x00,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    )
}

RESTORE_MOCO_ALL_REGISTERS = {
    1: CanopenRegister(
        identifier='', units='', subnode=1, idx=0x26DC, subidx=0x00,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    ),
    2: CanopenRegister(
        identifier='', units='', subnode=2, idx=0x2EDC, subidx=0x00,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    ),
    3: CanopenRegister(
        identifier='', units='', subnode=3, idx=0x36DC, subidx=0x00,
        cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    )
}

MONITORING_DIST_ENABLE = CanopenRegister(
    identifier='', units='', subnode=0, idx=0x58C0, subidx=0x00, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
)

MONITORING_NUMBER_MAPPED_REGISTERS = CanopenRegister(
    identifier='', units='', subnode=0, idx=0x58E3, subidx=0x00, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
)

MONITORING_REMOVE_DATA = CanopenRegister(
    identifier='', units='', subnode=0, idx=0x58EA, subidx=0x00, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.WO
)

MONITORING_BYTES_PER_BLOCK = CanopenRegister(
    identifier='', units='', subnode=0, idx=0x58E4, subidx=0x00, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
)

MONITORING_ACTUAL_NUMBER_BYTES = CanopenRegister(
    identifier='', units='', subnode=0, idx=0x58B7, subidx=0x00, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
)

MONITORING_DATA = CanopenRegister(
    identifier='', units='', subnode=0, idx=0x58B2, subidx=0x00, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
)

MONITORING_DISTURBANCE_VERSION = CanopenRegister(
    identifier='', units='', subnode=0, idx=0x58BA, subidx=0x00, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
)

DISTURBANCE_ENABLE = CanopenRegister(
    identifier='', units='', subnode=0, idx=0x58C7, subidx=0x00, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
)

DISTURBANCE_REMOVE_DATA = CanopenRegister(
    identifier='', units='', subnode=0, idx=0x58EB, subidx=0x00, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.WO
)

DISTURBANCE_NUMBER_MAPPED_REGISTERS = CanopenRegister(
    identifier='', units='', subnode=0, idx=0x58E8, subidx=0x00, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
)

DIST_DATA = CanopenRegister(
    identifier='', units='', subnode=0, idx=0x58B4, subidx=0x00, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
)

DIST_NUMBER_SAMPLES = CanopenRegister(
    identifier='', units='', subnode=0, idx=0x58C4, subidx=0x00, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
)


class ServoStatusListener(threading.Thread):
    """Reads the status word to check if the drive is alive.

    Args:
        servo (CanopenServo): Servo instance of the drive.

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
                        STATUS_WORD_REGISTERS[subnode], subnode=subnode
                    )
                    state = self.__servo.status_word_decode(status_word)
                    self.__servo._set_state(state, subnode=subnode)
                except Exception as e:
                    logger.error("Error getting drive status. "
                                 "Exception : %s", e)
            time.sleep(1.5)

    def stop(self):
        """Stops the loop that reads the status word register"""
        self.__stop = True


class CanopenServo(Servo):
    """CANopen Servo instance.

    Args:
        node (canopen.RemoteNode): Remote Node of the drive.
        dictionary_path (str): Path to the dictionary.
        servo_status_listener (bool): Boolean to initialize the ServoStatusListener and
            check the drive status.

    """
    def __init__(self, target, node, dictionary_path=None, eds=None,
                 servo_status_listener=False):
        super(CanopenServo, self).__init__(target)
        self.units_torque = None
        """SERVO_UNITS_TORQUE: Torque units."""
        self.units_pos = None
        """SERVO_UNITS_POS: Position units."""
        self.units_vel = None
        """SERVO_UNITS_VEL: Velocity units."""
        self.units_acc = None
        """SERVO_UNITS_ACC: Acceleration units."""
        self.__node = node
        if dictionary_path is not None:
            self._dictionary = CanopenDictionary(dictionary_path)
        else:
            self._dictionary = None
        self.eds = eds
        self.__lock = threading.RLock()
        self.__state = {
            1: lib.IL_SERVO_STATE_NRDY,
            2: lib.IL_SERVO_STATE_NRDY,
            3: lib.IL_SERVO_STATE_NRDY
        }
        self.__observers_servo_state = []
        self.__listener_servo_status = None

        self.__emcy_consumer = EmcyConsumer()

        if servo_status_listener:
            self.start_status_listener()

        prod_name = '' if self.dictionary.part_number is None \
            else self.dictionary.part_number
        self.full_name = '{} {}'.format(prod_name, self.name)
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

    def _get_reg(self, reg, subnode=1):
        """Validates a register.

        Args:
            reg (CanopenRegister): Targeted register to validate.
            subnode (int): Subnode for the register.

        Returns:
            CanopenRegister: Instance of the desired register from the dictionary.

        Raises:
            ILIOError: If the dictionary is not loaded.
            ILWrongRegisterError: If the register has invalid format.

        """
        if isinstance(reg, CanopenRegister):
            return reg
        elif isinstance(reg, str):
            _dict = self._dictionary
            if not _dict:
                raise_err(lib.IL_EIO, 'No dictionary loaded')
            if reg not in _dict.registers(subnode):
                raise_err(lib.IL_REGNOTFOUND, 'Register not found ({})'.format(reg))
            return _dict.registers(subnode)[reg]
        else:
            raise_err(lib.IL_EWRONGREG, 'Invalid register')

    def read(self, reg, subnode=1):
        """Read from servo.

        Args:
            reg (str, Register): Register.

        Returns:
            int: Error code of the read operation.

        Raises:
            TypeError: If the register type is not valid.
            ILAccessError: Wrong access to the register.
            ILIOError: Error reading the register.

        """
        _reg = self._get_reg(reg, subnode)
        raw_read = self._read_raw(reg, subnode)
        value = self.__convert_bytes_to_dtype(raw_read, _reg.dtype)
        if isinstance(value, str):
            value = value.replace('\x00', '')
        return value

    def write(self, reg, data, subnode=1):
        """Writes a data to a target register.

        Args:
            reg (CanopenRegister, str): Target register to be written.
            data (int, str, float): Data to be written.
            subnode (int): Target axis of the drive.

        Raises:
            ILAccessError: Wrong access to the register.
            ILIOError: Error reading the register.

        """
        _reg = self._get_reg(reg, subnode)
        value = self.__convert_dtype_to_bytes(data, _reg.dtype)
        self._write_raw(reg, value, subnode)

    def _write_raw(self, reg, data, subnode=1):
        """Writes a data to a target register.

        Args:
            reg (CanopenRegister, str): Target register to be written.
            data (int, str, float): Data to be written.
            subnode (int): Target axis of the drive.

        Raises:
            ILAccessError: Wrong access to the register.
            ILIOError: Error reading the register.

        """
        _reg = self._get_reg(reg, subnode)

        if _reg.access == REG_ACCESS.RO:
            raise_err(lib.IL_EACCESS, 'Register is Read-only')
        try:
            self.__lock.acquire()
            self.__node.sdo.download(_reg.idx,
                                     _reg.subidx,
                                     data)
        except Exception as e:
            logger.error("Failed writing %s. Exception: %s",
                         str(_reg.identifier), e)
            error_raised = "Error writing {}".format(_reg.identifier)
            raise_err(lib.IL_EIO, error_raised)
        finally:
            self.__lock.release()

    def _read_raw(self, reg, subnode=1):
        """Read raw bytes from servo.

        Args:
            reg (str, Register): Register.

        Returns:
            bytearray: Raw bytes reading from servo.

        Raises:
            ILAccessError: Wrong access to the register.
            ILIOError: Error reading the register.

        """
        _reg = self._get_reg(reg, subnode)

        access = _reg.access
        if access == REG_ACCESS.WO:
            raise_err(lib.IL_EACCESS, 'Register is Write-only')
        value = None
        try:
            self.__lock.acquire()
            value = self.__node.sdo.upload(_reg.idx, _reg.subidx)
        except Exception as e:
            logger.error("Failed reading %s. Exception: %s",
                         str(_reg.identifier), e)
            error_raised = f"Error reading {_reg.identifier}"
            raise_err(lib.IL_EIO, error_raised)
        finally:
            self.__lock.release()
        return value

    def enable(self, subnode=1, timeout=DEFAULT_PDS_TIMEOUT):
        """Enable PDS.

        Args:
            subnode (int): Subnode of the drive.
            timeout (int): Timeout in milliseconds.

       Raises:
            ILTimeoutError: The servo could not be enabled due to timeout.
            ILError: Failed to enable PDS.

        """
        r = 0

        status_word = self.read(STATUS_WORD_REGISTERS[subnode],
                                subnode=subnode)
        state = self.status_word_decode(status_word)
        self._set_state(state, subnode)

        # Try fault reset if faulty
        if self.status[subnode].value in [
            lib.IL_SERVO_STATE_FAULT,
            lib.IL_SERVO_STATE_FAULTR,
        ]:
            self.fault_reset(subnode=subnode)

        while self.status[subnode].value != lib.IL_SERVO_STATE_ENABLED:
            status_word = self.read(STATUS_WORD_REGISTERS[subnode],
                                    subnode=subnode)
            state = self.status_word_decode(status_word)
            self._set_state(state, subnode)
            if self.status[subnode].value != lib.IL_SERVO_STATE_ENABLED:
                # Check state and command action to reach enabled
                cmd = IL_MC_PDS_CMD_EO
                if self.status[subnode].value == lib.IL_SERVO_STATE_FAULT:
                    raise_err(lib.IL_ESTATE)
                elif self.status[subnode].value == lib.IL_SERVO_STATE_NRDY:
                    cmd = IL_MC_PDS_CMD_DV
                elif self.status[subnode].value == lib.IL_SERVO_STATE_DISABLED:
                    cmd = IL_MC_PDS_CMD_SD
                elif self.status[subnode].value == lib.IL_SERVO_STATE_RDY:
                    cmd = IL_MC_PDS_CMD_SOEO

                self.write(CONTROL_WORD_REGISTERS[subnode], cmd,
                           subnode=subnode)

                # Wait for state change
                r = self.status_word_wait_change(status_word, timeout,
                                                 subnode=subnode)
                if r < 0:
                    raise_err(r)

                # Read the current status word
                status_word = self.read(STATUS_WORD_REGISTERS[subnode],
                                        subnode=subnode)
                state = self.status_word_decode(status_word)
                self._set_state(state, subnode)
        raise_err(r)

    def disable(self, subnode=1, timeout=DEFAULT_PDS_TIMEOUT):
        """Disable PDS.

        Args:
            subnode (int): Subnode of the drive.
            timeout (int): Timeout in milliseconds.

        Raises:
            ILTimeoutError: The servo could not be disabled due to timeout.
            ILError: Failed to disable PDS.

        """
        r = 0

        status_word = self.read(STATUS_WORD_REGISTERS[subnode],
                                subnode=subnode)
        state = self.status_word_decode(status_word)
        self._set_state(state, subnode)

        while self.status[subnode].value != lib.IL_SERVO_STATE_DISABLED:
            state = self.status_word_decode(status_word)
            self._set_state(state, subnode)

            if self.status[subnode].value in [
                lib.IL_SERVO_STATE_FAULT,
                lib.IL_SERVO_STATE_FAULTR,
            ]:
                # Try fault reset if faulty
                self.fault_reset(subnode=subnode)
                status_word = self.read(STATUS_WORD_REGISTERS[subnode],
                                        subnode=subnode)
                state = self.status_word_decode(status_word)
                self._set_state(state, subnode)
            elif self.status[subnode].value != lib.IL_SERVO_STATE_DISABLED:
                # Check state and command action to reach disabled
                self.write(CONTROL_WORD_REGISTERS[subnode],
                           IL_MC_PDS_CMD_DV, subnode=subnode)

                # Wait until status word changes
                r = self.status_word_wait_change(status_word, timeout,
                                                 subnode=subnode)
                if r < 0:
                    raise_err(r)
                status_word = self.read(STATUS_WORD_REGISTERS[subnode],
                                        subnode=subnode)
                state = self.status_word_decode(status_word)
                self._set_state(state, subnode)
        raise_err(r)

    def fault_reset(self, subnode=1, timeout=DEFAULT_PDS_TIMEOUT):
        """Executes a fault reset on the drive.

        Args:
            subnode (int): Subnode of the drive.
            timeout (int): Timeout in milliseconds.

        Raises:
            ILTimeoutError: If fault reset spend too much time.
            ILError: Failed to fault reset.

        """
        r = 0
        status_word = self.read(STATUS_WORD_REGISTERS[subnode],
                                subnode=subnode)
        state = self.status_word_decode(status_word)
        if state.value in [
            lib.IL_SERVO_STATE_FAULT,
            lib.IL_SERVO_STATE_FAULTR,
        ]:
            # Check if faulty, if so try to reset (0->1)
            self.write(CONTROL_WORD_REGISTERS[subnode], 0, subnode=subnode)
            self.write(CONTROL_WORD_REGISTERS[subnode], IL_MC_CW_FR,
                       subnode=subnode)
            # Wait until status word changes
            r = self.status_word_wait_change(status_word, timeout,
                                             subnode=subnode)
            status_word = self.read(STATUS_WORD_REGISTERS[subnode],
                                    subnode=subnode)
            state = self.status_word_decode(status_word)
        self._set_state(state, subnode)
        raise_err(r)

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

    def replace_dictionary(self, dictionary):
        """Deletes and creates a new instance of the dictionary.

        Args:
            dictionary (str): Dictionary.

        """
        self._dictionary = CanopenDictionary(dictionary)

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

    def store_parameters(self, subnode=None, sdo_timeout=3):
        """Store all the current parameters of the target subnode.

        Args:
            subnode (int): Subnode of the axis. `None` by default which stores
            all the parameters.
            sdo_timeout (int): Timeout value for each SDO response.

        Raises:
            ILError: Invalid subnode.
            ILObjectNotExist: Failed to write to the registers.

        """
        r = 0
        self._change_sdo_timeout(sdo_timeout)

        try:
            if subnode is None:
                # Store all
                try:
                    self.write(reg=STORE_COCO_ALL,
                               data=PASSWORD_STORE_ALL,
                               subnode=0)
                    logger.info('Store all successfully done.')
                except Exception:
                    logger.warning('Store all COCO failed. Trying MOCO...')
                    r = -1
                if r < 0:
                    for dict_subnode in range(1, self.dictionary.subnodes):
                        self.write(
                            reg=STORE_MOCO_ALL_REGISTERS[dict_subnode],
                            data=PASSWORD_STORE_ALL,
                            subnode=dict_subnode)
                        logger.info(
                            'Store axis {} successfully done.'.format(
                                dict_subnode)
                        )
            elif subnode == 0:
                # Store subnode 0
                raise ILError('The current firmware version does not '
                              'have this feature implemented.')
            elif subnode > 0 and subnode in STORE_MOCO_ALL_REGISTERS:
                # Store axis
                self.write(reg=STORE_MOCO_ALL_REGISTERS[subnode],
                           data=PASSWORD_STORE_ALL,
                           subnode=subnode)
                logger.info('Store axis {} successfully done.'.format(subnode))
            else:
                raise ILError('Invalid subnode.')
        finally:
            sleep(1.5)
            self._change_sdo_timeout(CANOPEN_SDO_RESPONSE_TIMEOUT)

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
            self.write(reg=RESTORE_COCO_ALL,
                       data=PASSWORD_RESTORE_ALL,
                       subnode=0)
            logger.info('Restore all successfully done.')
        elif subnode == 0:
            # Restore subnode 0
            raise ILError('The current firmware version does not '
                          'have this feature implemented.')
        elif subnode > 0 and subnode in RESTORE_MOCO_ALL_REGISTERS:
            # Restore axis
            self.write(reg=RESTORE_COCO_ALL,
                       data=RESTORE_MOCO_ALL_REGISTERS[subnode],
                       subnode=subnode)
            logger.info('Restore subnode {} successfully done.'.format(subnode))
        else:
            raise ILError('Invalid subnode.')
        sleep(1.5)

    def _change_sdo_timeout(self, value):
        """Changes the SDO timeout of the node."""
        self.__node.sdo.RESPONSE_TIMEOUT = value

    def is_alive(self):
        """Checks if the servo responds to a reading a register.

        Returns:
            bool: Return code with the result of the read.

        """
        _is_alive = True
        try:
            self.read(STATUS_WORD_REGISTERS[1])
        except ILError as e:
            _is_alive = False
            logger.error(e)
        return _is_alive

    def get_state(self, subnode=1):
        """SERVO_STATE: Current drive state."""
        return self.__state[subnode], None

    def _set_state(self, state, subnode):
        """Sets the state internally.

        Args:
            state (SERVO_STATE): Current servo state.
            subnode (int): Subnode of the drive.

        """
        current_state = self.__state[subnode]
        if current_state != state:
            self.status[subnode] = state
            for callback in self.__observers_servo_state:
                callback(state, None, subnode)

    def start_status_listener(self):
        """Start listening for servo status events (SERVO_STATE)."""
        if self.__listener_servo_status is not None:
            return
        status_word = self.read(STATUS_WORD_REGISTERS[1])
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

    def subscribe_to_status(self, callback):
        """Subscribe to state changes.

            Args:
                callback (function): Callback function.

            Returns:
                int: Assigned slot.

        """
        if callback in self.__observers_servo_state:
            logger.info('Callback already subscribed.')
            return
        self.__observers_servo_state.append(callback)

    def unsubscribe_from_status(self, callback):
        """Unsubscribe from state changes.

        Args:
            callback (function): Callback function.

        """
        if callback not in self.__observers_servo_state:
            logger.info('Callback not subscribed.')
            return
        self.__observers_servo_state.remove(callback)

    def status_word_wait_change(self, status_word, timeout, subnode=1):
        """Waits for a status word change.

        Args:
            status_word (int): Status word to wait for.
            timeout (int): Maximum value to wait for the change.
            subnode (int): Subnode of the drive.

        Returns:
            int: Error code.

        """
        r = 0
        start_time = int(round(time.time() * 1000))
        actual_status_word = self.read(STATUS_WORD_REGISTERS[subnode],
                                       subnode=subnode)
        while actual_status_word == status_word:
            current_time = int(round(time.time() * 1000))
            time_diff = (current_time - start_time)
            if time_diff > timeout:
                r = lib.IL_ETIMEDOUT
                return r
            actual_status_word = self.read(
                STATUS_WORD_REGISTERS[subnode],
                subnode=subnode)
        return r

    def reload_errors(self, dictionary):
        """Force to reload all dictionary errors.

        Args:
            dictionary (str): Dictionary.

        """
        pass

    @staticmethod
    def status_word_decode(status_word):
        """Decodes the status word to a known value.

        Args:
            status_word (int): Read value for the status word.

        Returns:
            SERVO_STATE: Status word value.

        """
        if (status_word & IL_MC_PDS_STA_NRTSO_MSK) == IL_MC_PDS_STA_NRTSO:
            state = lib.IL_SERVO_STATE_NRDY
        elif (status_word & IL_MC_PDS_STA_SOD_MSK) == IL_MC_PDS_STA_SOD:
            state = lib.IL_SERVO_STATE_DISABLED
        elif (status_word & IL_MC_PDS_STA_RTSO_MSK) == IL_MC_PDS_STA_RTSO:
            state = lib.IL_SERVO_STATE_RDY
        elif (status_word & IL_MC_PDS_STA_SO_MSK) == IL_MC_PDS_STA_SO:
            state = lib.IL_SERVO_STATE_ON
        elif (status_word & IL_MC_PDS_STA_OE_MSK) == IL_MC_PDS_STA_OE:
            state = lib.IL_SERVO_STATE_ENABLED
        elif (status_word & IL_MC_PDS_STA_QSA_MSK) == IL_MC_PDS_STA_QSA:
            state = lib.IL_SERVO_STATE_QSTOP
        elif (status_word & IL_MC_PDS_STA_FRA_MSK) == IL_MC_PDS_STA_FRA:
            state = lib.IL_SERVO_STATE_FAULTR
        elif (status_word & IL_MC_PDS_STA_F_MSK) == IL_MC_PDS_STA_F:
            state = lib.IL_SERVO_STATE_FAULT
        else:
            state = lib.IL_SERVO_STATE_NRDY
        return SERVO_STATE(state)

    def __read_coco_moco_register(self, register_coco, register_moco):
        """Reads the COCO register and if it does not exist,
        reads the MOCO register

        Args:
            register_coco (IPBRegister): COCO Register to be read.
            register_moco (IPBRegister): MOCO Register to be read.

        Returns:
            int: Read value of the register.

        """
        try:
            return self.read(register_coco, subnode=0)
        except ILError:
            pass

        try:
            return self.read(register_moco, subnode=1)
        except ILError:
            pass

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
    def node(self):
        """canopen.RemoteNode: Remote node of the servo."""
        return self.__node

    @property
    def errors(self):
        """dict: Errors."""
        return self._dictionary.errors.errors

    @property
    def info(self):
        """dict: Servo information."""
        serial_number = self.__read_coco_moco_register(
            SERIAL_NUMBER_REGISTERS[0], SERIAL_NUMBER_REGISTERS[1])
        sw_version = self.__read_coco_moco_register(
            SOFTWARE_VERSION_REGISTERS[0], SOFTWARE_VERSION_REGISTERS[1])
        product_code = self.__read_coco_moco_register(
            PRODUCT_ID_REGISTERS[0], PRODUCT_ID_REGISTERS[1])
        revision_number = self.__read_coco_moco_register(
            REVISION_NUMBER_REGISTERS[0], REVISION_NUMBER_REGISTERS[1])
        hw_variant = 'A'

        return {
            'name': self.name,
            'serial_number': serial_number,
            'firmware_version': sw_version,
            'product_code': product_code,
            'revision_number': revision_number,
            'hw_variant': hw_variant
        }

    @property
    def status(self):
        """tuple: Servo status and state flags."""
        return self.__state

    @status.setter
    def status(self, new_state):
        self.__state = new_state

    @property
    def subnodes(self):
        """int: Number of subnodes."""
        return self._dictionary.subnodes

    def emcy_subscribe(self, cb):
        """Subscribe to emergency messages.

        Args:
            cb: Callback

        Returns:
            int: Assigned slot.

        """
        self.__emcy_consumer.add_callback(cb)

        return len(self.__emcy_consumer.callbacks) - 1

    def emcy_unsubscribe(self, slot):
        """Unsubscribe from emergency messages.

        Args:
            slot (int): Assigned slot when subscribed.

        """
        del self.__emcy_consumer.callbacks[slot]

    @property
    def monitoring_number_mapped_registers(self):
        """Get the number of mapped monitoring registers."""
        return self.__monitoring_num_mapped_registers

    def monitoring_enable(self):
        """Enable monitoring process."""
        self.write(MONITORING_DIST_ENABLE, data=1, subnode=0)

    def monitoring_disable(self):
        """Disable monitoring process."""
        self.write(MONITORING_DIST_ENABLE, data=0, subnode=0)

    def monitoring_remove_all_mapped_registers(self):
        """Remove all monitoring mapped registers."""
        self.write(MONITORING_NUMBER_MAPPED_REGISTERS, data=0, subnode=0)
        self.__monitoring_num_mapped_registers = \
            self.monitoring_get_num_mapped_registers()
        self.__monitoring_channels_size = {}
        self.__monitoring_channels_dtype = {}

    def monitoring_set_mapped_register(self, channel, address, subnode,
                                       dtype, size):
        """Set monitoring mapped register.

        Args:
            channel (int): Identity channel number.
            address (int): Register address to map.
            subnode (int): Subnode to be targeted.
            dtype (int): Register data type.
            size (int): Size of data in bytes.

        """
        self.__monitoring_channels_size[channel] = size
        self.__monitoring_channels_dtype[channel] = REG_DTYPE(dtype)
        data = self.__monitoring_disturbance_data_to_map_register(subnode,
                                                                  address,
                                                                  dtype,
                                                                  size)
        self.write(self.__monitoring_map_register(), data=data,
                   subnode=0)
        self.__monitoring_update_num_mapped_registers()
        self.__monitoring_num_mapped_registers = \
            self.monitoring_get_num_mapped_registers()
        self.write(MONITORING_NUMBER_MAPPED_REGISTERS,
                   data=self.monitoring_number_mapped_registers,
                   subnode=subnode)

    def __monitoring_map_register(self):
        """Get the first available Monitoring Mapped Register slot.

        Returns:
            str: Monitoring Mapped Register ID.

        """
        if self.monitoring_number_mapped_registers < 10:
            register_id = f'MON_CFG_REG' \
                          f'{self.monitoring_number_mapped_registers}_MAP'
        else:
            register_id = f'MON_CFG_REFG' \
                          f'{self.monitoring_number_mapped_registers}_MAP'
        return register_id

    def __monitoring_update_num_mapped_registers(self):
        """Update the number of mapped monitoring registers."""
        self.__monitoring_num_mapped_registers += 1
        self.write('MON_CFG_TOTAL_MAP',
                   data=self.__monitoring_num_mapped_registers,
                   subnode=0)

    def __monitoring_disturbance_map_can_address(self, address, subnode):
        """Map CAN register address to IPB register address."""
        return address - (0x2000 + (0x800 * (subnode - 1)))

    def monitoring_get_num_mapped_registers(self):
        """Obtain the number of monitoring mapped registers.

        Returns:
            int: Actual number of mapped registers.

        """
        return self.read('MON_CFG_TOTAL_MAP', 0)

    def monitoring_remove_data(self):
        """Remove monitoring data."""
        self.write(MONITORING_REMOVE_DATA,
                   data=1, subnode=0)

    def monitoring_get_bytes_per_block(self):
        """Obtain Bytes x Block configured.

        Returns:
            int: Actual number of Bytes x Block configured.

        """
        return self.read(MONITORING_BYTES_PER_BLOCK, subnode=0)

    def monitoring_read_data(self):
        """Obtain processed monitoring data.

        Returns:
            array: Actual processed monitoring data.

        """
        num_available_bytes = self.monitoring_actual_number_bytes()
        self.__monitoring_data = []
        while num_available_bytes > 0:
            if num_available_bytes < MONITORING_BUFFER_SIZE:
                limit = num_available_bytes
            else:
                limit = MONITORING_BUFFER_SIZE
            tmp_data = self.__monitoring_read_data()[:limit]
            self.__monitoring_data.append(tmp_data)
            num_available_bytes = self.monitoring_actual_number_bytes()
        self.__monitoring_process_data()

    def monitoring_actual_number_bytes(self):
        """Get the number of monitoring bytes left to be read."""
        return self.read(MONITORING_ACTUAL_NUMBER_BYTES, subnode=0)

    def __monitoring_read_data(self):
        """Read monitoring data frame."""
        return self._read_raw(MONITORING_DATA, subnode=0)

    def __monitoring_process_data(self):
        """Arrange monitoring data."""
        data_bytes = bytearray()
        for i in range(len(self.__monitoring_data)):
            data_bytes += self.__monitoring_data[i]
        bytes_per_block = self.monitoring_get_bytes_per_block()
        number_of_blocks = len(data_bytes) // bytes_per_block
        number_of_channels = self.monitoring_get_num_mapped_registers()
        res = [[] for _ in range(number_of_channels)]
        for block in range(number_of_blocks):
            block_data = data_bytes[block * bytes_per_block:
                                    block * bytes_per_block +
                                    bytes_per_block]
            for channel in range(number_of_channels):
                channel_data_size = self.__monitoring_channels_size[channel]
                val = self.__convert_bytes_to_dtype(
                    block_data[:channel_data_size],
                    self.__monitoring_channels_dtype[channel])
                res[channel].append(val)
                block_data = block_data[channel_data_size:]
        self.__processed_monitoring_data = res

    @staticmethod
    def __convert_bytes_to_dtype(data, dtype):
        """Convert data in bytes to corresponding dtype."""
        if dtype in [REG_DTYPE.S8,
                     REG_DTYPE.S16,
                     REG_DTYPE.S32]:
            value = int.from_bytes(
                data,
                "little",
                signed=True
            )
        elif dtype == REG_DTYPE.FLOAT:
            [value] = struct.unpack('f',
                                    data
                                    )
        elif dtype == REG_DTYPE.STR:
            value = data.decode("utf-8")
        else:
            value = int.from_bytes(
                data,
                "little"
            )
        return value

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
        return self.__processed_monitoring_data[channel]

    @property
    def monitoring_data_size(self):
        """Obtain monitoring data size.

        Returns:
            int: Current monitoring data size in bytes.

        """
        number_of_samples = self.read('MON_CFG_WINDOW_SAMP', subnode=0)
        return self.monitoring_get_bytes_per_block() * number_of_samples

    def disturbance_enable(self):
        """Enable disturbance process."""
        self.write(DISTURBANCE_ENABLE, data=1, subnode=0)

    def disturbance_disable(self):
        """Disable disturbance process."""
        self.write(DISTURBANCE_ENABLE, data=0, subnode=0)

    def disturbance_remove_data(self):
        """Remove disturbance data."""
        self.write(DISTURBANCE_REMOVE_DATA,
                   data=1, subnode=0)
        self.disturbance_data = bytearray()
        self.disturbance_data_size = 0

    def disturbance_remove_all_mapped_registers(self):
        """Remove all disturbance mapped registers."""
        self.write(DISTURBANCE_NUMBER_MAPPED_REGISTERS,
                   data=0, subnode=0)
        self.__disturbance_num_mapped_registers = \
            self.disturbance_get_num_mapped_registers()
        self.__disturbance_channels_size = {}
        self.__disturbance_channels_dtype = {}

    def disturbance_set_mapped_register(self, channel, address, subnode,
                                        dtype, size):
        """Set monitoring mapped register.

        Args:
            channel (int): Identity channel number.
            address (int): Register address to map.
            subnode (int): Subnode to be targeted.
            dtype (int): Register data type.
            size (int): Size of data in bytes.

        """
        self.__disturbance_channels_size[channel] = size
        self.__disturbance_channels_dtype[channel] = REG_DTYPE(dtype).name
        data = self.__monitoring_disturbance_data_to_map_register(subnode,
                                                                  address,
                                                                  dtype,
                                                                  size)
        self.write(self.__disturbance_map_register(), data=data,
                   subnode=0)
        self.__disturbance_update_num_mapped_registers()
        self.__disturbance_num_mapped_registers = \
            self.disturbance_get_num_mapped_registers()
        self.write(DISTURBANCE_NUMBER_MAPPED_REGISTERS,
                   data=self.disturbance_number_mapped_registers,
                   subnode=subnode)

    def disturbance_get_num_mapped_registers(self):
        """Obtain the number of disturbance mapped registers.

        Returns:
            int: Actual number of mapped registers.

        """
        return self.read('DIST_CFG_MAP_REGS', 0)

    def __disturbance_map_register(self):
        """Get the first available Disturbance Mapped Register slot.

        Returns:
            str: Disturbance Mapped Register ID.

        """
        return f'DIST_CFG_REG{self.disturbance_number_mapped_registers}_MAP'

    @property
    def disturbance_number_mapped_registers(self):
        """Get the number of mapped disturbance registers."""
        return self.__disturbance_num_mapped_registers

    def __disturbance_update_num_mapped_registers(self):
        """Update the number of mapped disturbance registers."""
        self.__disturbance_num_mapped_registers += 1
        self.write('DIST_CFG_MAP_REGS',
                   data=self.__disturbance_num_mapped_registers,
                   subnode=0)

    def __monitoring_disturbance_data_to_map_register(self, subnode, address,
                                                      dtype, size):
        """Arrange necessary data to map a monitoring/disturbance register.

        Args:
            subnode (int): Subnode to be targeted.
            address (int): Register address to map.
            dtype (int): Register data type.
            size (int): Size of data in bytes.

        """
        data_h = self.__monitoring_disturbance_map_can_address(
                     address, subnode) | subnode << 12
        data_l = dtype << 8 | size
        return (data_h << 16) | data_l

    @property
    def disturbance_data_size(self):
        """Obtain disturbance data size.

        Returns:
            int: Current disturbance data size.

        """
        return self.__disturbance_data_size

    @disturbance_data_size.setter
    def disturbance_data_size(self, value):
        """Set disturbance data size.

        Args:
            value (int): Disturbance data size in bytes.

        """
        self.__disturbance_data_size = value

    def disturbance_write_data(self, channels, dtypes, data_arr):
        """Write disturbance data.

        Args:
            channels (int or list of int): Channel identifier.
            dtypes (int or list of int): Data type.
            data_arr (list or list of list): Data array.

        """
        if not isinstance(channels, list):
            channels = [channels]
        if not isinstance(dtypes, list):
            dtypes = [dtypes]
        if not isinstance(data_arr[0], list):
            data_arr = [data_arr]
        num_samples = len(data_arr[0])
        self.write(DIST_NUMBER_SAMPLES, num_samples, subnode=0)
        data = bytearray()
        for sample_idx in range(num_samples):
            for channel in range(len(data_arr)):
                val = self.__convert_dtype_to_bytes(
                    data_arr[channel][sample_idx], dtypes[channel])
                data += val
        chunks = [data[i:i + CAN_MAX_WRITE_SIZE]
                  for i in range(0, len(data), CAN_MAX_WRITE_SIZE)]
        for chunk in chunks:
            self._write_raw(DIST_DATA, data=chunk, subnode=0)
        self.disturbance_data = data
        self.disturbance_data_size = len(data)

    @staticmethod
    def __convert_dtype_to_bytes(data, dtype):
        """Convert data in dtype to bytes.

        Args:
            data: Data to convert.
            dtype (REG_DTYPE): Data type.

        """
        # auto cast floats if register is not float
        if dtype == REG_DTYPE.FLOAT:
            data = float(data)
        elif dtype != REG_DTYPE.DOMAIN:
            data = int(data)

        if dtype == REG_DTYPE.FLOAT:
            data = struct.pack('f', data)
        elif dtype != REG_DTYPE.DOMAIN:
            bytes_length = 2
            signed = False
            if dtype == REG_DTYPE.U8:
                bytes_length = 1
            elif dtype == REG_DTYPE.S8:
                bytes_length = 1
                signed = True
            elif dtype == REG_DTYPE.U16:
                bytes_length = 2
            elif dtype == REG_DTYPE.S16:
                bytes_length = 2
                signed = True
            elif dtype == REG_DTYPE.U32:
                bytes_length = 4
            elif dtype == REG_DTYPE.S32:
                bytes_length = 4
                signed = True
            data = data.to_bytes(bytes_length,
                                 byteorder='little',
                                 signed=signed)
        return data

    @property
    def disturbance_data(self):
        """Obtain disturbance data.

        Returns:
            array: Current disturbance data.

        """
        return self.__disturbance_data

    @disturbance_data.setter
    def disturbance_data(self, value):
        """Set disturbance data.

        Args:
            value (array): Array with the disturbance to send.

        """
        self.__disturbance_data = value
