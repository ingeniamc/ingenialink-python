import time
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

import ingenialogger

try:
    import pysoem
except ImportError as ex:
    pysoem = None
    pysoem_import_error = ex

if TYPE_CHECKING:
    from pysoem import CdefSlave

from ingenialink.constants import CAN_MAX_WRITE_SIZE, CANOPEN_ADDRESS_OFFSET, MAP_ADDRESS_OFFSET
from ingenialink.ethercat.dictionary import EthercatDictionary
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.exceptions import ILIOError, ILTimeoutError
from ingenialink.pdo import PDOServo, RPDOMap, TPDOMap
from ingenialink.register import REG_ACCESS, REG_DTYPE

logger = ingenialogger.get_logger(__name__)


class SDO_OPERATION_MSG(Enum):
    """Message for exceptions depending on the operation type."""

    READ = "reading"
    WRITE = "writing"


class EthercatServo(PDOServo):
    """Ethercat Servo instance.

    Args:
        slave: Slave to be connected.
        slave_id: Slave ID.
        dictionary_path: Path to the dictionary.
        connection_timeout: Time in seconds of the connection timeout.
        servo_status_listener: Toggle the listener of the servo for
            its status, errors, faults, etc.

    Raises:
        ImportError: WinPcap is not installed

    """

    DICTIONARY_CLASS = EthercatDictionary
    MAX_WRITE_SIZE = CAN_MAX_WRITE_SIZE

    TIMEOUT_WORKING_COUNTER = -5
    NOFRAME_WORKING_COUNTER = 0

    MONITORING_DATA = EthercatRegister(
        identifier="MONITORING_DATA",
        units="",
        subnode=0,
        idx=0x58B2,
        subidx=0x01,
        cyclic="CONFIG",
        dtype=REG_DTYPE.U16,
        access=REG_ACCESS.RO,
    )
    DIST_DATA = EthercatRegister(
        identifier="DISTURBANCE_DATA",
        units="",
        subnode=0,
        idx=0x58B4,
        subidx=0x01,
        cyclic="CONFIG",
        dtype=REG_DTYPE.U16,
        access=REG_ACCESS.WO,
    )

    RPDO_ASSIGN_REGISTER_SUB_IDX_0 = EthercatRegister(
        identifier="RPDO_ASSIGN_REGISTER",
        units="",
        subnode=0,
        idx=0x1C12,
        subidx=0x00,
        dtype=REG_DTYPE.S32,
        access=REG_ACCESS.RW,
    )
    RPDO_ASSIGN_REGISTER_SUB_IDX_1 = EthercatRegister(
        identifier="RPDO_ASSIGN_REGISTER",
        units="",
        subnode=0,
        idx=0x1C12,
        subidx=0x01,
        dtype=REG_DTYPE.S32,
        access=REG_ACCESS.RW,
    )
    RPDO_MAP_REGISTER_SUB_IDX_0 = [
        EthercatRegister(
            identifier="RPDO_MAP_REGISTER",
            units="",
            subnode=0,
            idx=0x1600,
            subidx=0x00,
            dtype=REG_DTYPE.S32,
            access=REG_ACCESS.RW,
        )
    ]
    RPDO_MAP_REGISTER_SUB_IDX_1 = [
        EthercatRegister(
            identifier="RPDO_MAP_REGISTER",
            units="",
            subnode=0,
            idx=0x1600,
            subidx=0x01,
            dtype=REG_DTYPE.STR,
            access=REG_ACCESS.RW,
        )
    ]
    TPDO_ASSIGN_REGISTER_SUB_IDX_0 = EthercatRegister(
        identifier="TPDO_ASSIGN_REGISTER",
        units="",
        subnode=0,
        idx=0x1C13,
        subidx=0x00,
        dtype=REG_DTYPE.S32,
        access=REG_ACCESS.RW,
    )
    TPDO_ASSIGN_REGISTER_SUB_IDX_1 = EthercatRegister(
        identifier="TPDO_ASSIGN_REGISTER",
        units="",
        subnode=0,
        idx=0x1C13,
        subidx=0x01,
        dtype=REG_DTYPE.S32,
        access=REG_ACCESS.RW,
    )
    TPDO_MAP_REGISTER_SUB_IDX_0 = [
        EthercatRegister(
            identifier="TPDO_MAP_REGISTER",
            units="",
            subnode=0,
            idx=0x1A00,
            subidx=0x00,
            dtype=REG_DTYPE.S32,
            access=REG_ACCESS.RW,
        )
    ]
    TPDO_MAP_REGISTER_SUB_IDX_1 = [
        EthercatRegister(
            identifier="TPDO_MAP_REGISTER",
            units="",
            subnode=0,
            idx=0x1A00,
            subidx=0x01,
            dtype=REG_DTYPE.STR,
            access=REG_ACCESS.RW,
        )
    ]

    def __init__(
        self,
        slave: "CdefSlave",
        slave_id: int,
        dictionary_path: str,
        connection_timeout: float,
        servo_status_listener: bool = False,
    ):
        if not pysoem:
            raise pysoem_import_error
        self.__slave = slave
        self.slave_id = slave_id
        self._connection_timeout = connection_timeout
        super(EthercatServo, self).__init__(slave_id, dictionary_path, servo_status_listener)

    def _read_raw(  # type: ignore [override]
        self,
        reg: EthercatRegister,
        buffer_size: int = 0,
        complete_access: bool = False,
        start_time: float = time.time(),
    ) -> bytes:
        self._lock.acquire()
        try:
            value: bytes = self.__slave.sdo_read(reg.idx, reg.subidx, buffer_size, complete_access)
        except (
            pysoem.SdoError,
            pysoem.MailboxError,
            pysoem.PacketError,
            pysoem.WkcError,
            ILIOError,
        ) as e:
            self._handle_sdo_exception(reg, SDO_OPERATION_MSG.READ, e)
        except pysoem.Emergency as e:
            if time.time() < start_time + self._connection_timeout:
                return self._read_raw(reg, buffer_size, complete_access, start_time)
            raise ILTimeoutError("Emergency messages could not be cleared.") from e
        finally:
            self._lock.release()
        return value

    def _write_raw(self, reg: EthercatRegister, data: bytes, complete_access: bool = False, start_time: float = time.time()) -> None:  # type: ignore [override]
        self._lock.acquire()
        try:
            self.__slave.sdo_write(reg.idx, reg.subidx, data, complete_access)
        except (
            pysoem.SdoError,
            pysoem.MailboxError,
            pysoem.PacketError,
            pysoem.WkcError,
            ILIOError,
        ) as e:
            self._handle_sdo_exception(reg, SDO_OPERATION_MSG.WRITE, e)
        except pysoem.Emergency as e:
            if time.time() < start_time + self._connection_timeout:
                return self._write_raw(reg, data, complete_access, start_time)
            raise ILTimeoutError("Emergency messages could not be cleared.") from e
        finally:
            self._lock.release()

    def _handle_sdo_exception(
        self, reg: EthercatRegister, operation_msg: SDO_OPERATION_MSG, exception: Exception
    ) -> None:
        """
        Handle the exceptions that occur when reading or writing SDOs.

        Args:
            reg: The register that was read or written.
            operation_msg: Operation type message to be shown on the exception.
            exception: The exception that occurred while reading or writing.

        Raises:
            ILIOError: If the register cannot be read or written.
            ILIOError: If the slave fails acknowledge the command.
            ILTimeoutError: If the slave fails to respond within the connection
             timeout period.

        """
        if isinstance(
            exception, (pysoem.SdoError, pysoem.MailboxError, pysoem.PacketError, ILIOError)
        ):
            raise ILIOError(
                f"Error {operation_msg} {reg.identifier}. Reason: {exception}"
            ) from exception
        elif isinstance(exception, pysoem.WkcError):
            if exception.wkc == self.NOFRAME_WORKING_COUNTER:
                raise ILIOError(f"Error {operation_msg} data: No frame.") from exception
            if exception.wkc == self.TIMEOUT_WORKING_COUNTER:
                raise ILTimeoutError(f"Timeout {operation_msg} data.") from exception

    def _monitoring_read_data(self) -> bytes:  # type: ignore [override]
        """Read monitoring data frame."""
        return self._read_raw(self.MONITORING_DATA, buffer_size=1024, complete_access=True)

    def _disturbance_write_data(self, data: bytearray) -> None:  # type: ignore [override]
        """Write disturbance data."""
        return self._write_raw(self.DIST_DATA, bytes(data), complete_access=True)

    @staticmethod
    def __monitoring_disturbance_map_can_address(address: int, subnode: int) -> int:
        """Map CAN register address to IPB register address.

        Args:
            subnode: Subnode to be targeted.
            address: Register address to map.

        """
        mapped_address: int = address - (
            CANOPEN_ADDRESS_OFFSET + (MAP_ADDRESS_OFFSET * (subnode - 1))
        )
        return mapped_address

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
        ipb_address = self.__monitoring_disturbance_map_can_address(address, subnode)
        mapped_address: int = super()._monitoring_disturbance_data_to_map_register(
            subnode, ipb_address, dtype, size
        )
        return mapped_address

    def _get_emergency_description(self, error_code: int) -> Optional[str]:
        """Get the error description from the error code.
        Args:
            error_code: Error code received.
        Returns:
            The error description corresponding to the error code.
        """
        error_description = None
        if self.dictionary.errors is not None:
            error_code &= 0xFFFF
            if error_code in self.dictionary.errors.errors:
                error_description = self.dictionary.errors.errors[error_code][-1]
        return error_description

    def set_pdo_map_to_slave(self, rpdo_maps: List[RPDOMap], tpdo_maps: List[TPDOMap]) -> None:
        self.reset_rpdo_mapping()
        self.reset_tpdo_mapping()
        self._rpdo_maps = rpdo_maps
        self._tpdo_maps = tpdo_maps
        self.slave.config_func = self.map_pdos

    def process_pdo_inputs(self) -> None:
        self._process_tpdo(self.__slave.input)

    def generate_pdo_outputs(self) -> None:
        output = self._process_rpdo()
        if output is None:
            return
        self.__slave.output = self._process_rpdo()

    @property
    def slave(self) -> "CdefSlave":
        """Ethercat slave"""
        return self.__slave
