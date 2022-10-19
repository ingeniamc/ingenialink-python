import threading
import canopen
from canopen.emcy import EmcyConsumer

from ..constants import *
from ..exceptions import *
from .._ingenialink import lib
from ingenialink.utils._utils import raise_err,\
    convert_bytes_to_dtype, convert_dtype_to_bytes
from ..servo import Servo
from .dictionary import CanopenDictionary
from .register import CanopenRegister, REG_DTYPE, REG_ACCESS

import ingenialogger
logger = ingenialogger.get_logger(__name__)

CANOPEN_SDO_RESPONSE_TIMEOUT = 0.3

MONITORING_DATA = CanopenRegister(
    identifier='', units='', subnode=0, idx=0x58B2, subidx=0x00, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
)

MONITORING_DISTURBANCE_VERSION = CanopenRegister(
    identifier='', units='', subnode=0, idx=0x58BA, subidx=0x00, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
)

DIST_DATA = CanopenRegister(
    identifier='', units='', subnode=0, idx=0x58B4, subidx=0x00, cyclic='CONFIG',
    dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
)


class CanopenServo(Servo):
    """CANopen Servo instance.

    Args:
        node (canopen.RemoteNode): Remote Node of the drive.
        dictionary_path (str): Path to the dictionary.
        eds (str): Path to the eds file.
        servo_status_listener (bool): Toggle the listener of the servo for
            its status, errors, faults, etc.

    """
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
    RESTORE_COCO_ALL = CanopenRegister(
        identifier='', units='', subnode=0, idx=0x1011, subidx=0x01, cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    )
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
    STORE_COCO_ALL = CanopenRegister(
        identifier='', units='', subnode=0, idx=0x1010, subidx=0x01, cyclic='CONFIG',
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
    MONITORING_DIST_ENABLE = CanopenRegister(
        identifier='', units='', subnode=0, idx=0x58C0, subidx=0x00, cyclic='CONFIG',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
    )
    MONITORING_REMOVE_DATA = CanopenRegister(
        identifier='', units='', subnode=0, idx=0x58EA, subidx=0x00, cyclic='CONFIG',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.WO
    )
    MONITORING_NUMBER_MAPPED_REGISTERS = CanopenRegister(
        identifier='', units='', subnode=0, idx=0x58E3, subidx=0x00, cyclic='CONFIG',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
    )
    MONITORING_BYTES_PER_BLOCK = CanopenRegister(
        identifier='', units='', subnode=0, idx=0x58E4, subidx=0x00, cyclic='CONFIG',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
    )
    MONITORING_ACTUAL_NUMBER_BYTES = CanopenRegister(
        identifier='', units='', subnode=0, idx=0x58B7, subidx=0x00, cyclic='CONFIG',
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
    DIST_NUMBER_SAMPLES = CanopenRegister(
        identifier='', units='', subnode=0, idx=0x58C4, subidx=0x00, cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    )

    def __init__(self, target, node, dictionary_path=None, eds=None,
                 servo_status_listener=False):
        self.eds = eds
        self.__node = node
        self.__emcy_consumer = EmcyConsumer()
        if dictionary_path is not None:
            self._dictionary = CanopenDictionary(dictionary_path)
        else:
            self._dictionary = None
        self.__lock = threading.RLock()
        super(CanopenServo, self).__init__(target)

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
        value = convert_bytes_to_dtype(raw_read, _reg.dtype)
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
        value = convert_dtype_to_bytes(data, _reg.dtype)
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

    def replace_dictionary(self, dictionary):
        """Deletes and creates a new instance of the dictionary.

        Args:
            dictionary (str): Dictionary.

        """
        self._dictionary = CanopenDictionary(dictionary)

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
        self._change_sdo_timeout(sdo_timeout)
        super().store_parameters(subnode)
        self._change_sdo_timeout(CANOPEN_SDO_RESPONSE_TIMEOUT)

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
            self.read(self.STATUS_WORD_REGISTERS[1])
        except ILError as e:
            _is_alive = False
            logger.error(e)
        return _is_alive

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

    def reload_errors(self, dictionary):
        """Force to reload all dictionary errors.

        Args:
            dictionary (str): Dictionary.

        """
        pass

    @property
    def node(self):
        """canopen.RemoteNode: Remote node of the servo."""
        return self.__node

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

    @staticmethod
    def __monitoring_disturbance_map_can_address(address, subnode):
        """Map CAN register address to IPB register address."""
        return address - (0x2000 + (0x800 * (subnode - 1)))

    def __monitoring_read_data(self):
        """Read monitoring data frame."""
        return self._read_raw(MONITORING_DATA, subnode=0)

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

    def disturbance_write_data(self, channels, dtypes, data_arr):
        """Write disturbance data.

        Args:
            channels (int or list of int): Channel identifier.
            dtypes (int or list of int): Data type.
            data_arr (list or list of list): Data array.

        """
        data, chunks = self.__disturbance_create_data_chunks(channels,
                                                             dtypes,
                                                             data_arr,
                                                             CAN_MAX_WRITE_SIZE)
        for chunk in chunks:
            self._write_raw(DIST_DATA, data=chunk, subnode=0)
        self.disturbance_data = data
        self.disturbance_data_size = len(data)
