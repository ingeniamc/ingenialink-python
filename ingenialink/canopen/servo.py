import os
import time
import threading
import canopen
import struct
import xml.etree.ElementTree as ET

from ingenialink.utils._utils import *
from .constants import *
from ..constants import *
from ..exceptions import *
from .._ingenialink import lib
from ..servo import SERVO_STATE, Servo
from .dictionary import CanopenDictionary
from .register import CanopenRegister, REG_DTYPE, REG_ACCESS

import ingenialogger
logger = ingenialogger.get_logger(__name__)

CANOPEN_SDO_RESPONSE_TIMEOUT = 0.3

SERIAL_NUMBER = CanopenRegister(
    identifier='', units='', subnode=1, idx=0x26E6, subidx=0x00,
    cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
)
PRODUCT_CODE = CanopenRegister(
    identifier='', units='', subnode=1, idx=0x26E1, subidx=0x00,
    cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
)
SOFTWARE_VERSION = CanopenRegister(
    identifier='', units='', subnode=1, idx=0x26E4, subidx=0x00,
    cyclic='CONFIG', dtype=REG_DTYPE.STR, access=REG_ACCESS.RO
)
REVISION_NUMBER = CanopenRegister(
    identifier='', units='', subnode=1, idx=0x26E2, subidx=0x00,
    cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
)

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
                 servo_status_listener=True):
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

        if servo_status_listener:
            status_word = self.read(STATUS_WORD_REGISTERS[1])
            state = self.status_word_decode(status_word)
            self._set_state(state, 1)

            self.__listener_servo_status = ServoStatusListener(self)
            self.__listener_servo_status.start()

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
            _reg = reg
            return _reg
        elif isinstance(reg, str):
            _dict = self._dictionary
            if not _dict:
                raise_err(lib.IL_EIO, 'No dictionary loaded')
            if reg not in _dict.registers(subnode):
                raise_err(lib.IL_REGNOTFOUND, 'Register not found ({})'.format(reg))
            _reg = _dict.registers(subnode)[reg]
            return _reg
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

        access = _reg.access
        if access == REG_ACCESS.WO:
            raise_err(lib.IL_EACCESS, 'Register is Write-only')

        value = None
        dtype = _reg.dtype
        error_raised = None
        try:
            self.__lock.acquire()
            if dtype == REG_DTYPE.S8:
                value = int.from_bytes(
                    self.__node.sdo.upload(_reg.idx,
                                           _reg.subidx),
                    "little",
                    signed=True
                )
            elif dtype == REG_DTYPE.S16:
                value = int.from_bytes(
                    self.__node.sdo.upload(_reg.idx,
                                           _reg.subidx),
                    "little",
                    signed=True
                )
            elif dtype == REG_DTYPE.S32:
                value = int.from_bytes(
                    self.__node.sdo.upload(_reg.idx,
                                           _reg.subidx),
                    "little",
                    signed=True
                )
            elif dtype == REG_DTYPE.FLOAT:
                [value] = struct.unpack('f',
                                        self.__node.sdo.upload(
                                            _reg.idx,
                                            _reg.subidx)
                                        )
            elif dtype == REG_DTYPE.STR:
                value = self.__node.sdo.upload(
                    _reg.idx,
                    _reg.subidx
                ).decode("utf-8")
            else:
                value = int.from_bytes(
                    self.__node.sdo.upload(_reg.idx,
                                           _reg.subidx),
                    "little"
                )
        except Exception as e:
            logger.error("Failed reading %s. Exception: %s",
                         str(_reg.identifier), e)
            error_raised = "Error reading {}".format(_reg.identifier)
        finally:
            self.__lock.release()

        if error_raised is not None:
            raise_err(lib.IL_EIO, error_raised)

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
            TypeError: If the register type is not valid.
            ILAccessError: Wrong access to the register.
            ILIOError: Error reading the register.
        """
        _reg = self._get_reg(reg, subnode)

        if _reg.access == REG_ACCESS.RO:
            raise_err(lib.IL_EACCESS, 'Register is Read-only')

        # auto cast floats if register is not float
        if _reg.dtype == REG_DTYPE.FLOAT:
            data = float(data)
        elif _reg.dtype != REG_DTYPE.DOMAIN:
            data = int(data)

        error_raised = None
        try:
            self.__lock.acquire()
            if _reg.dtype == REG_DTYPE.FLOAT:
                self.__node.sdo.download(_reg.idx,
                                         _reg.subidx,
                                         struct.pack('f', data))
            elif _reg.dtype == REG_DTYPE.DOMAIN:
                self.__node.sdo.download(_reg.idx,
                                         _reg.subidx, data)
            else:
                bytes_length = 2
                signed = False
                if _reg.dtype == REG_DTYPE.U8:
                    bytes_length = 1
                elif _reg.dtype == REG_DTYPE.S8:
                    bytes_length = 1
                    signed = True
                elif _reg.dtype == REG_DTYPE.U16:
                    bytes_length = 2
                elif _reg.dtype == REG_DTYPE.S16:
                    bytes_length = 2
                    signed = True
                elif _reg.dtype == REG_DTYPE.U32:
                    bytes_length = 4
                elif _reg.dtype == REG_DTYPE.S32:
                    bytes_length = 4
                    signed = True

                self.__node.sdo.download(_reg.idx,
                                         _reg.subidx,
                                         data.to_bytes(bytes_length,
                                                       byteorder='little',
                                                       signed=signed))
        except Exception as e:
            logger.error("Failed reading %s. Exception: %s",
                         str(_reg.identifier), e)
            error_raised = "Error writing {}".format(_reg.identifier)
        finally:
            self.__lock.release()

        if error_raised is not None:
            raise_err(lib.IL_EIO, error_raised)

    def enable(self, timeout=2000, subnode=1):
        """Enable PDS.

        Args:
            timeout (int): Maximum value to wait for the operation to be done.
            subnode (int): Subnode of the drive.

        Returns:
            int: Error code.
        """
        r = 0

        status_word = self.read(STATUS_WORD_REGISTERS[subnode],
                                subnode=subnode)
        state = self.status_word_decode(status_word)
        self._set_state(state, subnode)

        # Try fault reset if faulty
        if self.status[subnode].value == lib.IL_SERVO_STATE_FAULT or \
                self.status[subnode].value == lib.IL_SERVO_STATE_FAULTR:
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
                r = self.status_word_wait_change(status_word, PDS_TIMEOUT,
                                                 subnode=1)
                if r < 0:
                    raise_err(r)

                # Read the current status word
                status_word = self.read(STATUS_WORD_REGISTERS[subnode],
                                        subnode=subnode)
                state = self.status_word_decode(status_word)
                self._set_state(state, subnode)
        raise_err(r)

    def disable(self, subnode=1):
        """Disable PDS.

        Args:
            subnode (int): Subnode of the drive.

        Returns:
            int: Error code.
        """
        r = 0

        status_word = self.read(STATUS_WORD_REGISTERS[subnode],
                                subnode=subnode)
        state = self.status_word_decode(status_word)
        self._set_state(state, subnode)

        while self.status[subnode].value != lib.IL_SERVO_STATE_DISABLED:
            state = self.status_word_decode(status_word)
            self._set_state(state, subnode)

            if self.status[subnode].value == lib.IL_SERVO_STATE_FAULT or \
                    self.status[subnode].value == lib.IL_SERVO_STATE_FAULTR:
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
                r = self.status_word_wait_change(status_word, PDS_TIMEOUT,
                                                 subnode=1)
                if r < 0:
                    raise_err(r)
                status_word = self.read(STATUS_WORD_REGISTERS[subnode],
                                        subnode=subnode)
                state = self.status_word_decode(status_word)
                self._set_state(state, subnode)
        raise_err(r)

    def fault_reset(self, subnode=1):
        """Executes a fault reset on the drive.

        Args:
            subnode (int): Subnode of the drive.

        Raises:
            ILTimeoutError: If fault reset spend too much time.

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
            r = self.status_word_wait_change(status_word, PDS_TIMEOUT,
                                             subnode=1)
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

        with open(self._dictionary.path, 'r') as xml_file:
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

    def load_configuration(self, config_file, subnode=None):
        """Write current dictionary storage to the servo drive.

        Args:
            config_file (str): Path to the dictionary.
            subnode (int): Subnode of the axis.

        """
        if not os.path.isfile(config_file):
            raise FileNotFoundError('Could not find {}.'.format(config_file))
        if subnode is not None and (not isinstance(subnode, int) or subnode < 0):
            raise ILError('Invalid subnode')
        with open(config_file, 'r') as xml_file:
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

        r = -1
        for element in registers:
            try:
                if 'storage' in element.attrib and element.attrib['access'] == 'rw':
                    element_subnode = int(element.attrib['subnode'])
                    if subnode is None or subnode == element_subnode:
                        r = 0
                        print('Loading subnode {}'.format(element_subnode))
                        self.write(element.attrib['id'],
                                   float(element.attrib['storage']),
                                   subnode=element_subnode
                                   )
            except BaseException as e:
                logger.error("Exception during load_configuration, register "
                             "%s: %s", str(element.attrib['id']), e)
        if r < 0:
            raise ILError('Could not find subnode {} '
                          'in the configuration file'.format(subnode))

    def store_parameters(self, subnode=0, sdo_timeout=3):
        """Store all the current parameters of the target subnode.

        Args:
            subnode (int): Subnode of the axis.
            sdo_timeout (int): Timeout value for each SDO response.

        Raises:
            ILError: Invalid subnode.
            ILObjectNotExist: Failed to write to the registers.
        """
        r = 0
        self._change_sdo_timeout(sdo_timeout)

        try:
            if subnode == 0:
                # Store all
                try:
                    self.write(reg=STORE_COCO_ALL,
                               data=PASSWORD_STORE_ALL,
                               subnode=subnode)
                    logger.info('Store all successfully done.')
                except Exception as e:
                    logger.warning('Store all COCO failed. Trying MOCO...')
                    r = -1
                if r < 0:
                    if self._dictionary.subnodes > SINGLE_AXIS_MINIMUM_SUBNODES:
                        # Multiaxis
                        for dict_subnode in self._dictionary.subnodes:
                            self.write(reg=STORE_MOCO_ALL_REGISTERS[dict_subnode],
                                       data=PASSWORD_STORE_ALL,
                                       subnode=dict_subnode)
                            logger.info('Store axis {} successfully done.'.format(
                                dict_subnode))
                    else:
                        # Single axis
                        self.write(reg=STORE_MOCO_ALL_REGISTERS[1],
                                   data=PASSWORD_STORE_ALL,
                                   subnode=1)
                        logger.info('Store all successfully done.')
            elif subnode > 0:
                # Store axis
                self.write(reg=STORE_MOCO_ALL_REGISTERS[subnode],
                           data=PASSWORD_STORE_ALL,
                           subnode=subnode)
                logger.info('Store axis {} successfully done.'.format(subnode))
            else:
                raise ILError('Invalid subnode.')
        finally:
            self._change_sdo_timeout(CANOPEN_SDO_RESPONSE_TIMEOUT)

    def restore_parameters(self):
        """Restore all the current parameters of all the slave to default.

        Raises:
            ILError: Invalid subnode.
            ILObjectNotExist: Failed to write to the registers.
        """
        self.write(reg=RESTORE_COCO_ALL,
                   data=PASSWORD_RESTORE_ALL,
                   subnode=0)
        logger.info('Restore all successfully done.')

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

    def _change_sdo_timeout(self, value):
        """Changes the SDO timeout of the node."""
        self.__node.sdo.RESPONSE_TIMEOUT = value

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

    def subscribe_to_status(self, callback):
        """Subscribe to state changes.

            Args:
                callback (Callback): Callback function.

            Returns:
                int: Assigned slot.
        """
        if callback in self.__observers_servo_state:
            raise ILError('Callback already subscribed.')
        slot = len(self.__observers_servo_state)
        self.__observers_servo_state.append(callback)
        return slot

    def unsubscribe_from_status(self, callback):
        """Unsubscribe from state changes.

        Args:
            callback (Callback): Callback function.

        """
        if callback not in self.__observers_servo_state:
            raise ILError('Callback not subscribed.')
        self.__observers_servo_state.remove(callback)

    def stop_servo_monitor(self):
        """Stops the ServoStatusListener."""
        if self.__listener_servo_status is not None and \
                self.__listener_servo_status.is_alive():
            self.__listener_servo_status.stop()
            self.__listener_servo_status.join()
            self.__listener_servo_status = None

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
                                       subnode=1)
        while actual_status_word == status_word:
            current_time = int(round(time.time() * 1000))
            time_diff = (current_time - start_time)
            if time_diff > timeout:
                r = lib.IL_ETIMEDOUT
                return r
            actual_status_word = self.read(
                STATUS_WORD_REGISTERS[subnode],
                subnode=1)
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
        serial_number = self.read(SERIAL_NUMBER)
        product_code = self.read(PRODUCT_CODE)
        sw_version = self.read(SOFTWARE_VERSION)
        revision_number = self.read(REVISION_NUMBER)
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