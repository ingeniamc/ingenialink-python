from typing import Optional

from pysoem import CdefSlave, SdoError, MailboxError, PacketError
import ingenialogger

from ingenialink.exceptions import ILIOError
from ingenialink.servo import Servo
from ingenialink.canopen.dictionary import CanopenDictionary
from ingenialink.canopen.register import CanopenRegister, REG_DTYPE, REG_ACCESS
from ingenialink.constants import CAN_MAX_WRITE_SIZE

logger = ingenialogger.get_logger(__name__)


class EthercatServo(Servo):  # type: ignore
    """Ethercat Servo instance.

    Args:
        slave: Slave to be connected.
        slave_id: Slave ID.
        dictionary_path: Path to the dictionary.
        servo_status_listener: Toggle the listener of the servo for
            its status, errors, faults, etc.

    """

    DICTIONARY_CLASS = CanopenDictionary
    MAX_WRITE_SIZE = CAN_MAX_WRITE_SIZE
    WRONG_WORKING_COUNTER = -1

    STATUS_WORD_REGISTERS = "CIA402_DRV_STATE_STATUS"
    RESTORE_COCO_ALL = "CIA301_COMMS_RESTORE_ALL"
    STORE_COCO_ALL = "CIA301_COMMS_STORE_ALL"
    MONITORING_DATA = CanopenRegister(
        identifier="MONITORING_DATA",
        units="",
        subnode=0,
        idx=0x58B2,
        subidx=0x01,
        cyclic="CONFIG",
        dtype=REG_DTYPE.U16,
        access=REG_ACCESS.RO,
    )
    DIST_DATA = CanopenRegister(
        identifier="DISTURBANCE_DATA",
        units="",
        subnode=0,
        idx=0x58B4,
        subidx=0x01,
        cyclic="CONFIG",
        dtype=REG_DTYPE.U16,
        access=REG_ACCESS.WO,
    )

    def __init__(
        self,
        slave: CdefSlave,
        slave_id: int,
        dictionary_path: Optional[str] = None,
        servo_status_listener: bool = False,
    ):
        self.__slave = slave
        self.slave_id = slave_id
        super(EthercatServo, self).__init__(slave.name, dictionary_path, servo_status_listener)

    def _read_raw(
        self, reg: CanopenRegister, buffer_size: int = 0, complete_access: bool = False
    ) -> bytes:
        self._lock.acquire()
        try:
            value: bytes = self.__slave.sdo_read(reg.idx, reg.subidx, buffer_size, complete_access)
            self._check_working_counter()
        except (SdoError, MailboxError, PacketError, ILIOError) as e:
            raise ILIOError(f"Error reading {reg.identifier}. Reason: {e}") from e
        finally:
            self._lock.release()
        return value

    def _write_raw(self, reg: CanopenRegister, data: bytes, complete_access: bool = False) -> None:
        self._lock.acquire()
        try:
            self.__slave.sdo_write(reg.idx, reg.subidx, data, complete_access)
            self._check_working_counter()
        except (SdoError, MailboxError, PacketError, ILIOError) as e:
            raise ILIOError(f"Error writing {reg.identifier}. Reason: {e}") from e
        finally:
            self._lock.release()

    def _monitoring_read_data(self) -> bytes:
        """Read monitoring data frame."""
        return self._read_raw(self.MONITORING_DATA, buffer_size=1024, complete_access=True)

    def _disturbance_write_data(self, data: bytearray) -> None:
        """Write disturbance data."""
        return self._write_raw(self.DIST_DATA, bytes(data), complete_access=True)

    @staticmethod
    def __monitoring_disturbance_map_can_address(address: int, subnode: int) -> int:
        """Map CAN register address to IPB register address.

        Args:
            subnode: Subnode to be targeted.
            address: Register address to map.

        """
        return address - (0x2000 + (0x800 * (subnode - 1)))

    def _monitoring_disturbance_data_to_map_register(
        self, subnode: int, address: int, dtype: REG_DTYPE, size: int
    ) -> int:
        """Arrange necessary data to map a monitoring/disturbance register.

        Args:
            subnode: Subnode to be targeted.
            address: Register address to map.
            dtype: Register data type.
            size: Size of data in bytes.

        """
        ipb_address = self.__monitoring_disturbance_map_can_address(address, subnode)
        mapped_address: int = super()._monitoring_disturbance_data_to_map_register(
            subnode, ipb_address, dtype, size
        )
        return mapped_address

    def _check_working_counter(self) -> None:
        """Check if the slave responds with a correct working counter.

        Raises:
            ILIOError: If the received working counter is incorrect.

        """
        if self.__slave.mbx_receive() == self.WRONG_WORKING_COUNTER:
            raise ILIOError("Wrong working counter")

    @property
    def slave(self) -> CdefSlave:
        """Ethercat slave"""
        return self.__slave
