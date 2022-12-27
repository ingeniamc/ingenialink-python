import canopen
from canopen.emcy import EmcyConsumer

from ingenialink.constants import CAN_MAX_WRITE_SIZE
from ingenialink.exceptions import ILAccessError, ILIOError
from ingenialink.utils._utils import convert_bytes_to_dtype, convert_dtype_to_bytes
from ingenialink.servo import Servo
from ingenialink.canopen.dictionary import CanopenDictionary
from ingenialink.canopen.register import CanopenRegister
from ingenialink.enums.register import REG_DTYPE, REG_ACCESS

import ingenialogger
logger = ingenialogger.get_logger(__name__)

CANOPEN_SDO_RESPONSE_TIMEOUT = 0.3


class CanopenServo(Servo):
    """CANopen Servo instance.

    Args:
        target (int): Node ID to be connected.
        node (canopen.RemoteNode): Remote Node of the drive.
        dictionary_path (str): Path to the dictionary.
        eds (str): Path to the eds file.
        servo_status_listener (bool): Toggle the listener of the servo for
            its status, errors, faults, etc.

    """
    STATUS_WORD_REGISTERS = "CIA402_DRV_STATE_STATUS"
    RESTORE_COCO_ALL = "CIA301_COMMS_RESTORE_ALL"
    STORE_COCO_ALL = "CIA301_COMMS_STORE_ALL"
    MONITORING_DATA = CanopenRegister(
        identifier='', units='', subnode=0, idx=0x58B2, subidx=0x00, cyclic='CONFIG',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
    )
    DIST_DATA = CanopenRegister(
        identifier='', units='', subnode=0, idx=0x58B4, subidx=0x00, cyclic='CONFIG',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
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
        super(CanopenServo, self).__init__(target, servo_status_listener)

    def read(self, reg, subnode=1):
        _reg = self._get_reg(reg, subnode)
        raw_read = self._read_raw(reg, subnode)
        value = convert_bytes_to_dtype(raw_read, _reg.dtype)
        if isinstance(value, str):
            value = value.replace('\x00', '')
        return value

    def write(self, reg, data, subnode=1):
        _reg = self._get_reg(reg, subnode)
        value = convert_dtype_to_bytes(data, _reg.dtype)
        self._write_raw(reg, value, subnode)

    def replace_dictionary(self, dictionary):
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
            raise ILAccessError('Register is Read-only')
        try:
            self._lock.acquire()
            self.__node.sdo.download(_reg.idx,
                                     _reg.subidx,
                                     data)
        except Exception as e:
            logger.error("Failed writing %s. Exception: %s",
                         str(_reg.identifier), e)
            error_raised = "Error writing {}".format(_reg.identifier)
            raise ILIOError(error_raised)
        finally:
            self._lock.release()

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
            raise ILAccessError('Register is Write-only')
        value = None
        try:
            self._lock.acquire()
            value = self.__node.sdo.upload(_reg.idx, _reg.subidx)
        except Exception as e:
            logger.error("Failed reading %s. Exception: %s",
                         str(_reg.identifier), e)
            error_raised = f"Error reading {_reg.identifier}"
            raise ILIOError(error_raised)
        finally:
            self._lock.release()
        return value

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

    def disturbance_write_data(self, channels, dtypes, data_arr):
        data, chunks = self._disturbance_create_data_chunks(channels,
                                                            dtypes,
                                                            data_arr,
                                                            CAN_MAX_WRITE_SIZE)
        for chunk in chunks:
            self._write_raw(self.DIST_DATA, data=chunk, subnode=0)
        self.disturbance_data = data
        self.disturbance_data_size = len(data)

    def _change_sdo_timeout(self, value):
        """Changes the SDO timeout of the node."""
        self.__node.sdo.RESPONSE_TIMEOUT = value

    @staticmethod
    def __monitoring_disturbance_map_can_address(address, subnode):
        """Map CAN register address to IPB register address."""
        return address - (0x2000 + (0x800 * (subnode - 1)))

    def _monitoring_read_data(self):
        return self._read_raw(self.MONITORING_DATA, subnode=0)

    def _monitoring_disturbance_data_to_map_register(self, subnode, address,
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
    def node(self):
        """canopen.RemoteNode: Remote node of the servo."""
        return self.__node

