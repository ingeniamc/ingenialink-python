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
        servo_status_listener (bool): Toggle the listener of the servo for
            its status, errors, faults, etc.

    """

    DICTIONARY_CLASS = CanopenDictionary
    MAX_WRITE_SIZE = CAN_MAX_WRITE_SIZE

    STATUS_WORD_REGISTERS = "CIA402_DRV_STATE_STATUS"
    RESTORE_COCO_ALL = "CIA301_COMMS_RESTORE_ALL"
    STORE_COCO_ALL = "CIA301_COMMS_STORE_ALL"
    MONITORING_DATA = CanopenRegister(
        idx=0x58B2,
        subidx=0x00,
        cyclic="CONFIG",
        dtype=REG_DTYPE.U16,
        access=REG_ACCESS.RO,
        subnode=0,
    )
    DIST_DATA = CanopenRegister(
        idx=0x58B4,
        subidx=0x00,
        cyclic="CONFIG",
        dtype=REG_DTYPE.U16,
        access=REG_ACCESS.RW,
        subnode=0,
    )

    def __init__(self, target, node, dictionary_path=None, servo_status_listener=False):
        self.__node = node
        self.__emcy_consumer = EmcyConsumer()
        super(CanopenServo, self).__init__(target, dictionary_path, servo_status_listener)

    def read(self, reg, subnode=1):
        value = super().read(reg, subnode=subnode)
        if isinstance(value, str):
            value = value.replace("\x00", "")
        return value

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

    def _write_raw(self, reg, data):
        try:
            self._lock.acquire()
            self.__node.sdo.download(reg.idx, reg.subidx, data)
        except Exception as e:
            logger.error("Failed writing %s. Exception: %s", str(reg.identifier), e)
            error_raised = f"Error writing {reg.identifier}"
            raise ILIOError(error_raised) from e
        finally:
            self._lock.release()

    def _read_raw(self, reg):
        try:
            self._lock.acquire()
            value = self.__node.sdo.upload(reg.idx, reg.subidx)
        except Exception as e:
            logger.error("Failed reading %s. Exception: %s", str(reg.identifier), e)
            error_raised = f"Error reading {reg.identifier}"
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

    def _change_sdo_timeout(self, value):
        """Changes the SDO timeout of the node."""
        self.__node.sdo.RESPONSE_TIMEOUT = value

    @staticmethod
    def __monitoring_disturbance_map_can_address(address, subnode):
        """Map CAN register address to IPB register address."""
        return address - (0x2000 + (0x800 * (subnode - 1)))

    def _monitoring_disturbance_data_to_map_register(self, subnode, address, dtype, size):
        """Arrange necessary data to map a monitoring/disturbance register.

        Args:
            subnode (int): Subnode to be targeted.
            address (int): Register address to map.
            dtype (int): Register data type.
            size (int): Size of data in bytes.

        """
        ipb_address = self.__monitoring_disturbance_map_can_address(address, subnode)
        return super()._monitoring_disturbance_data_to_map_register(
            subnode, ipb_address, dtype, size
        )

    @property
    def node(self):
        """canopen.RemoteNode: Remote node of the servo."""
        return self.__node
