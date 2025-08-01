import os
from enum import Enum
from typing import TYPE_CHECKING, Callable, Optional, Union

import ingenialogger
from typing_extensions import override

from ingenialink import Servo
from ingenialink.emcy import EmergencyMessage
from ingenialink.ethercat.dictionary import EthercatDictionary

try:
    import pysoem
except ImportError as ex:
    pysoem = None
    pysoem_import_error = ex

if TYPE_CHECKING:
    from pysoem import CdefSlave

from ingenialink.constants import (
    CAN_MAX_WRITE_SIZE,
    ECAT_STATE_CHANGE_TIMEOUT_US,
)
from ingenialink.dictionary import CanOpenObject, Interface
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.exceptions import ILEcatStateError, ILIOError
from ingenialink.pdo import PDOServo, RPDOMap, TPDOMap

logger = ingenialogger.get_logger(__name__)


class SdoOperationMsg(Enum):
    """Message for exceptions depending on the operation type."""

    READ = "reading"
    WRITE = "writing"


class EthercatEmergencyMessage(EmergencyMessage):
    """Ethercat emergency message class.

    Args:
        servo: The servo that generated the emergency error.
        emergency_msg: The emergency message instance from PySOEM.
    """

    def __init__(self, servo: Servo, emergency_msg: "pysoem.Emergency"):
        data = (
            emergency_msg.b1.to_bytes(1, "little")
            + emergency_msg.w1.to_bytes(2, "little")
            + emergency_msg.w2.to_bytes(2, "little")
        )
        super().__init__(servo, emergency_msg.error_code, emergency_msg.error_reg, data)


class EthercatServo(PDOServo):
    """Ethercat Servo instance.

    Args:
        slave: Slave to be connected.
        slave_id: Slave ID.
        dictionary_path: Path to the dictionary.
        connection_timeout: Time in seconds of the connection timeout.
        servo_status_listener: Toggle the listener of the servo for
            its status, errors, faults, etc.
        sdo_read_write_release_gil: True to release the GIL in SDO read/write operations,
            False otherwise. If not specified, default pysoem configuration will be used.
        disconnect_callback: Callback function to be called when the servo is disconnected.
            If not specified, no callback will be called.

    Raises:
        ImportError: WinPcap is not installed

    """

    MAX_WRITE_SIZE = CAN_MAX_WRITE_SIZE
    MONITORING_DATA_BUFFER_SIZE = 1024

    NO_RESPONSE_WORKING_COUNTER = 0
    TIMEOUT_WORKING_COUNTER = -5
    NOFRAME_WORKING_COUNTER = -1
    UNKNOWN_FRAME_WORKING_COUNTER = -2

    ETHERCAT_PDO_WATCHDOG = "processdata"
    SECONDS_TO_MS_CONVERSION_FACTOR = 1000

    interface = Interface.ECAT

    DEFAULT_STORE_RECOVERY_TIMEOUT = 1

    DEFAULT_EEPROM_OPERATION_TIMEOUT_uS = 200_000
    DEFAULT_EEPROM_READ_BYTES_LENGTH = 2

    def __init__(
        self,
        slave: "CdefSlave",
        slave_id: int,
        dictionary_path: str,
        servo_status_listener: bool = False,
        sdo_read_write_release_gil: Optional[bool] = None,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ):
        if not pysoem:
            raise pysoem_import_error
        self.__slave: CdefSlave = slave
        self.slave_id = slave_id
        self.__emcy_observers: list[Callable[[EmergencyMessage], None]] = []
        self.__slave.add_emergency_callback(self._on_emcy)
        self.__sdo_read_write_release_gil = sdo_read_write_release_gil
        super().__init__(
            slave_id,
            dictionary_path,
            servo_status_listener,
            disconnect_callback=disconnect_callback,
        )

    @property  # type: ignore[misc]
    def dictionary(self) -> EthercatDictionary:  # type: ignore[override]
        """Ethercat dictionary."""
        return self._dictionary  # type: ignore[return-value]

    def teardown(self) -> None:
        """Perform the necessary actions for teardown."""
        self._lock.acquire()
        self.stop_status_listener()

        # Remove the servo reference from the pdo maps
        for rpdo_map in self._rpdo_maps:
            rpdo_map.slave = None
        for tpdo_map in self._tpdo_maps:
            tpdo_map.slave = None
        self.__slave = None
        self._lock.release()

    def check_servo_is_in_preoperational_state(self) -> None:
        """Checks if the servo is in preoperational state.

        Raises:
            ILEcatStateError: if servo is not in preoperational state.
        """
        if self.slave is None or not pysoem:
            return
        if (
            self.slave.state_check(pysoem.PREOP_STATE, ECAT_STATE_CHANGE_TIMEOUT_US)
            != pysoem.PREOP_STATE
        ):
            raise ILEcatStateError(
                f"Servo is in {self.slave.state} state, PDOMap can not be modified."
            )

    def _read_raw(  # type: ignore [override]
        self,
        reg: EthercatRegister,
        buffer_size: int = 0,
        complete_access: bool = False,
        *,
        release_gil: Optional[bool] = None,
    ) -> bytes:
        if release_gil is None:
            release_gil = self.__sdo_read_write_release_gil
        self._lock.acquire()
        try:
            value: bytes = self.__slave.sdo_read(
                reg.idx, reg.subidx, buffer_size, complete_access, release_gil=release_gil
            )
        except (
            pysoem.SdoError,
            pysoem.MailboxError,
            pysoem.PacketError,
            pysoem.WkcError,
            ILIOError,
        ) as e:
            self._handle_sdo_exception(reg, SdoOperationMsg.READ, e)
        except AttributeError:
            raise ILIOError(f"Error reading {reg.identifier}. The drive has been disconnected.")
        finally:
            self._lock.release()
        return value

    def _write_raw(  # type: ignore [override]
        self,
        reg: EthercatRegister,
        data: bytes,
        complete_access: bool = False,
        *,
        release_gil: Optional[bool] = None,
    ) -> None:
        if release_gil is None:
            release_gil = self.__sdo_read_write_release_gil
        self._lock.acquire()
        try:
            self.__slave.sdo_write(
                reg.idx, reg.subidx, data, complete_access, release_gil=release_gil
            )
        except (
            pysoem.SdoError,
            pysoem.MailboxError,
            pysoem.PacketError,
            pysoem.WkcError,
            ILIOError,
        ) as e:
            self._handle_sdo_exception(reg, SdoOperationMsg.WRITE, e)
        except AttributeError:
            raise ILIOError(f"Error writing {reg.identifier}. The drive has been disconnected.")
        finally:
            self._lock.release()

    def _handle_sdo_exception(
        self, reg: EthercatRegister, operation_msg: SdoOperationMsg, exception: Exception
    ) -> None:
        """Handle the exceptions that occur when reading or writing SDOs.

        Args:
            reg: The register that was read or written.
            operation_msg: Operation type message to be shown on the exception.
            exception: The exception that occurred while reading or writing.

        Raises:
            ILIOError: If the register cannot be read or written.
            ILIOError: If the slave fails to acknowledge the command.
            ILIOError: If the working counter value is wrong.
        """
        default_error_msg = f"Error {operation_msg.value} {reg.identifier}"
        if isinstance(exception, pysoem.WkcError):
            wkc_errors = {
                self.NO_RESPONSE_WORKING_COUNTER: "The working counter remained unchanged.",
                self.NOFRAME_WORKING_COUNTER: "No frame.",
                self.TIMEOUT_WORKING_COUNTER: "Timeout.",
                self.UNKNOWN_FRAME_WORKING_COUNTER: "Unknown frame received.",
            }
            reason = wkc_errors.get(exception.wkc, f"Working counter: {exception.wkc}")
        elif isinstance(exception, (pysoem.SdoError, pysoem.MailboxError, pysoem.PacketError)):
            reason = f"{type(exception).__name__}: Slave {exception.slave_pos}, "
            if isinstance(exception, pysoem.SdoError):
                reason += f"Abort code {exception.abort_code}, "
            else:
                reason += f"Error code {exception.error_code}, "
            error_description = f"Error description: {exception.desc}."
            reason += error_description
        else:
            reason = str(exception)
        raise ILIOError(f"{default_error_msg}. {reason}") from exception

    def _monitoring_read_data(self) -> bytes:
        """Read monitoring data frame.

        Raises:
            NotImplementedError: If monitoring is not supported by the device.
            ValueError: If unexpected data type was returned from read.

        Returns:
            Monitoring data.
        """
        if not super()._is_monitoring_implemented():
            raise NotImplementedError("Monitoring is not supported by this device.")
        if not isinstance(
            data := self.read_complete_access(
                self.MONITORING_DATA,
                subnode=0,
                buffer_size=self.MONITORING_DATA_BUFFER_SIZE,
            ),
            bytes,
        ):
            raise ValueError(
                f"Error reading monitoring data. Expected type bytes, got {type(data)}"
            )
        return data

    def _disturbance_write_data(self, data: bytes) -> None:
        """Write disturbance data.

        Args:
            data: Data to be written.

        """
        if not super()._is_disturbance_implemented():
            raise NotImplementedError("Disturbance is not supported by this device.")
        return self.write_complete_access(self.DIST_DATA, subnode=0, data=data)

    def emcy_subscribe(self, callback: Callable[[EmergencyMessage], None]) -> None:
        """Subscribe to emergency messages.

        Args:
            callback: Callable that takes a EmergencyMessage instance as argument.

        """
        self.__emcy_observers.append(callback)

    def emcy_unsubscribe(self, callback: Callable[[EmergencyMessage], None]) -> None:
        """Unsubscribe from emergency messages.

        Args:
            callback: Subscribed callback.

        """
        self.__emcy_observers.remove(callback)

    def _on_emcy(self, emergency_msg: "pysoem.Emergency") -> None:
        """Receive an emergency message from PySOEM and transform it to a EthercatEmergencyMessage.

        Afterward, send the EthercatEmergencyMessage to all the subscribed callbacks.

        Args:
            emergency_msg: The pysoem.Emergency instance.

        """
        emergency_message = EthercatEmergencyMessage(self, emergency_msg)
        logger.warning(f"Emergency message received from slave {self.target}: {emergency_message}")
        for callback in self.__emcy_observers:
            callback(emergency_message)

    def read_rpdo_map_from_slave(
        self, map_obj: Union[str, CanOpenObject], subnode: int = 0, buffer_size: Optional[int] = 0
    ) -> RPDOMap:
        """Read the RPDO map from the slave.

        Args:
            map_obj: UID or object of the RPDO map.
            subnode: Subnode of the rpdo map.
            buffer_size: Size of the buffer to read the pdo map.

        Returns:
            RPDOMap: The RPDO map read from the slave.
        """
        if isinstance(map_obj, str):
            map_obj = self.dictionary.get_object(map_obj, subnode)
        value = self.read_complete_access(map_obj, subnode, buffer_size)
        return RPDOMap.from_pdo_value(value, map_obj, self.dictionary)

    def read_tpdo_map_from_slave(
        self,
        map_obj: Union[str, CanOpenObject],
        subnode: int = 0,
        buffer_size: Optional[int] = None,
    ) -> TPDOMap:
        """Read the TPDO map from the slave.

        Args:
            map_obj: UID or object of the RPDO map.
            subnode: Subnode of the rpdo map.
            buffer_size: Size of the buffer to read the pdo map.

        Returns:
            TPDOMap: The TPDO map read from the slave.
        """
        if isinstance(map_obj, str):
            map_obj = self.dictionary.get_object(map_obj, subnode)
        value = self.read_complete_access(map_obj, subnode, buffer_size)
        return TPDOMap.from_pdo_value(value, map_obj, self.dictionary)

    @override
    def set_pdo_map_to_slave(self, rpdo_maps: list[RPDOMap], tpdo_maps: list[TPDOMap]) -> None:
        for rpdo_map in rpdo_maps:
            if rpdo_map not in self._rpdo_maps:
                rpdo_map.slave = self
                self._rpdo_maps.append(rpdo_map)
        for tpdo_map in tpdo_maps:
            if tpdo_map not in self._tpdo_maps:
                tpdo_map.slave = self
                self._tpdo_maps.append(tpdo_map)
        self.slave.config_func = self.map_pdos

    @override
    def process_pdo_inputs(self) -> None:
        self._process_tpdo(self.__slave.input)

    @override
    def generate_pdo_outputs(self) -> None:
        self.__slave.output = self._process_rpdo()

    def set_pdo_watchdog_time(self, timeout: float) -> None:
        """Set the process data watchdog time.

        Args:
            timeout: Time in seconds.

        """
        self.slave.set_watchdog(
            self.ETHERCAT_PDO_WATCHDOG, self.SECONDS_TO_MS_CONVERSION_FACTOR * timeout
        )

    def _read_esc_eeprom(
        self,
        address: int,
        length: int = DEFAULT_EEPROM_READ_BYTES_LENGTH,
        timeout: int = DEFAULT_EEPROM_OPERATION_TIMEOUT_uS,
    ) -> bytes:
        """Read from the ESC EEPROM.

        Args:
            address: EEPROM address to be read.
            length: Length of data to be read. By default, 2 bytes are read.
            timeout: Operation timeout (microseconds). By default, 200.000 us.

        Returns:
            EEPROM data. The read data.

        Raises:
            ValueError: If the length to be read has an invalid value.

        """
        if length < 1:
            raise ValueError("The minimum length is 1 byte.")
        data = b""
        while len(data) < length:
            data += self.slave.eeprom_read(address, timeout)
            address += 2
        if len(data) > length:
            data = data[:length]
        return data

    def _write_esc_eeprom(
        self, address: int, data: bytes, timeout: int = DEFAULT_EEPROM_OPERATION_TIMEOUT_uS
    ) -> None:
        """Write to the ESC EEPROM.

        Args:
            address: EEPROM address to be written.
            data: Data to be written. The data length must be a multiple of 2 bytes.
            timeout: Operation timeout (microseconds). By default, 200.000 us.

        Raises:
            ValueError: If the data has the wrong size.

        """
        if len(data) % 2 != 0:
            raise ValueError("The data length must be a multiple of 2 bytes.")
        start_address = address
        while data:
            self.slave.eeprom_write(start_address, data[:2], timeout)
            data = data[2:]
            start_address += 1

    def _write_esc_eeprom_from_file(self, file_path: str) -> None:
        """Load a binary file to the ESC EEPROM.

        Args:
            file_path: Path to the binary file to be loaded.

        Raises:
            FileNotFoundError: If the binary file cannot be found.

        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Could not find {file_path}.")
        with open(file_path, "rb") as file:
            data = file.read()
        self._write_esc_eeprom(address=0, data=data)

    @property
    def slave(self) -> "CdefSlave":
        """Ethercat slave."""
        return self.__slave
