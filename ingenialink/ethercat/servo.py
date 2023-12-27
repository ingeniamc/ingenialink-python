from typing import Optional, Any

from pysoem import CdefSlave, SdoError, MailboxError, PacketError, Emergency
import ingenialogger

from ingenialink.exceptions import ILIOError
from ingenialink.servo import Servo
from ingenialink.ethercat.dictionary import EthercatDictionary
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.ethercat.pdo import PDOMapper, PDOMap
from ingenialink.register import REG_DTYPE, REG_ACCESS
from ingenialink.constants import CAN_MAX_WRITE_SIZE, CANOPEN_ADDRESS_OFFSET, MAP_ADDRESS_OFFSET
from ingenialink.utils._utils import convert_dtype_to_bytes, convert_bytes_to_dtype, dtype_value

logger = ingenialogger.get_logger(__name__)


class EthercatServo(Servo):
    """Ethercat Servo instance.

    Args:
        slave: Slave to be connected.
        slave_id: Slave ID.
        dictionary_path: Path to the dictionary.
        servo_status_listener: Toggle the listener of the servo for
            its status, errors, faults, etc.

    """

    DICTIONARY_CLASS = EthercatDictionary
    MAX_WRITE_SIZE = CAN_MAX_WRITE_SIZE
    WRONG_WORKING_COUNTER = -1

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

    def __init__(
        self,
        slave: CdefSlave,
        slave_id: int,
        dictionary_path: str,
        servo_status_listener: bool = False,
    ):
        self.__slave = slave
        self.slave_id = slave_id
        self.pdo_map: Optional[PDOMap] = None
        super(EthercatServo, self).__init__(slave_id, dictionary_path, servo_status_listener)

    def _read_raw(  # type: ignore [override]
        self, reg: EthercatRegister, buffer_size: int = 0, complete_access: bool = False
    ) -> bytes:
        self._lock.acquire()
        try:
            value: bytes = self.__slave.sdo_read(reg.idx, reg.subidx, buffer_size, complete_access)
            self._check_working_counter()
        except (SdoError, MailboxError, PacketError, ILIOError) as e:
            raise ILIOError(f"Error reading {reg.identifier}. Reason: {e}") from e
        except Emergency as e:
            error_description = self._get_emergency_description(e.error_code)
            if error_description is None:
                error_description = e
            raise ILIOError(f"Error reading {reg.identifier}. Reason: {error_description}") from e
        finally:
            self._lock.release()
        return value

    def _write_raw(self, reg: EthercatRegister, data: bytes, complete_access: bool = False) -> None:  # type: ignore [override]
        self._lock.acquire()
        try:
            self.__slave.sdo_write(reg.idx, reg.subidx, data, complete_access)
            self._check_working_counter()
        except (SdoError, MailboxError, PacketError, ILIOError) as e:
            raise ILIOError(f"Error writing {reg.identifier}. Reason: {e}") from e
        except Emergency as e:
            error_description = self._get_emergency_description(e.error_code)
            if error_description is None:
                error_description = e
            raise ILIOError(f"Error writing {reg.identifier}. Reason: {error_description}") from e
        finally:
            self._lock.release()

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

    def _check_working_counter(self) -> None:
        """Check if the slave responds with a correct working counter.

        Raises:
            ILIOError: If the received working counter is incorrect.

        """
        if self.__slave.mbx_receive() == self.WRONG_WORKING_COUNTER:
            raise ILIOError("Wrong working counter")

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

    def create_pdo_map(self) -> PDOMap:
        return PDOMap(self.dictionary)

    def map_pdo(self, pdo_map: PDOMap) -> Any:
        self.pdo_map = pdo_map
        pdo_mapper = PDOMapper(self, self.pdo_map)
        return pdo_mapper.set_slave_mapping()

    def process_pdo_inputs(self) -> None:
        if self.pdo_map is None:
            return
        input_data = self.__slave.input
        for pdo_map_item in self.pdo_map.tpdo_registers:
            reg_dtype = pdo_map_item.register.dtype
            data_size = dtype_value[reg_dtype][0]
            data = input_data[:data_size]
            input_data = input_data[data_size:]
            pdo_map_item.value = convert_bytes_to_dtype(data, reg_dtype)
            pdo_map_item.callback(pdo_map_item)

    def generate_pdo_outputs(self) -> None:
        if self.pdo_map is None:
            return
        output = bytes()
        for pdo_map_item in self.pdo_map.rpdo_registers:
            reg_dtype = pdo_map_item.register.dtype
            pdo_map_item.value = pdo_map_item.callback(pdo_map_item)
            output += convert_dtype_to_bytes(pdo_map_item.value, reg_dtype)
        self.__slave.output = output

    @property
    def slave(self) -> CdefSlave:
        """Ethercat slave"""
        return self.__slave
