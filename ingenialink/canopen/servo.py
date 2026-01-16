import contextlib
from collections.abc import Iterator
from typing import Callable, Optional, Union

import canopen
import ingenialogger
from canopen.emcy import EmcyError
from typing_extensions import override

from ingenialink import RegDtype
from ingenialink.canopen.register import CanopenRegister
from ingenialink.configuration_file import ConfigRegister, ConfigurationFile
from ingenialink.constants import CAN_MAX_WRITE_SIZE
from ingenialink.dictionary import Interface
from ingenialink.emcy import EmergencyMessage
from ingenialink.exceptions import ILIOError
from ingenialink.register import Register
from ingenialink.servo import Servo
from ingenialink.utils._utils import convert_bytes_to_dtype, convert_dtype_to_bytes

logger = ingenialogger.get_logger(__name__)

CANOPEN_SDO_RESPONSE_TIMEOUT = 0.3


class CanopenEmergencyMessage(EmergencyMessage):
    """Canopen emergency message class.

    Args:
        servo: The servo that generated the emergency error.
        emergency_msg: The emergency message instance from canopen.
    """

    def __init__(self, servo: Servo, emergency_msg: EmcyError):
        super().__init__(servo, emergency_msg.code, emergency_msg.register, emergency_msg.data)


class CanopenServo(Servo):
    """CANopen Servo instance.

    Args:
        target: Node ID to be connected.
        node: Remote Node of the drive.
        dictionary_path: Path to the dictionary.
        servo_status_listener: Toggle the listener of the servo for
            its status, errors, faults, etc.
        disconnect_callback: Callback function to be called when the servo is disconnected.
            If not specified, no callback will be called.

    """

    MAX_WRITE_SIZE = CAN_MAX_WRITE_SIZE

    STATUS_WORD_REGISTERS = "DRV_STATE_STATUS"
    RESTORE_COCO_ALL = "CIA301_COMMS_RESTORE_ALL"
    STORE_COCO_ALL = "CIA301_COMMS_STORE_ALL"

    interface = Interface.CAN

    def __init__(
        self,
        target: int,
        node: canopen.RemoteNode,
        dictionary_path: str,
        servo_status_listener: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ) -> None:
        self.__node = node
        self.__emcy_observers: list[Callable[[EmergencyMessage], None]] = []
        self.__node.emcy.add_callback(self._on_emcy)
        super().__init__(
            target, dictionary_path, servo_status_listener, disconnect_callback=disconnect_callback
        )

    @override
    def read(
        self,
        reg: Union[str, Register],
        subnode: int = 1,
    ) -> Union[int, float, str, bytes]:
        value = super().read(reg, subnode=subnode)
        if isinstance(value, str):
            value = value.replace("\x00", "")
        return value

    def store_parameters(self, subnode: Optional[int] = None, sdo_timeout: int = 3) -> None:
        """Store all the current parameters of the target subnode.

        Args:
            subnode: Subnode of the axis. `None` by default which stores all the parameters.
            sdo_timeout: Timeout value for each SDO response.
                Drive takes longer to respond while storing parameters.
                The value is temporarily set to this value and then rolled back to the original one.
        """
        with self._minimum_sdo_timeout(sdo_timeout):
            super().store_parameters(subnode)

    def _write_raw(self, reg: CanopenRegister, data: bytes) -> None:  # type: ignore [override]
        try:
            self._lock.acquire()
            self.__node.sdo.download(reg.idx, reg.subidx, data)
        except Exception as e:
            logger.error("Failed writing %s. Exception: %s", str(reg.identifier), e)
            error_raised = f"Error writing {reg.identifier}"
            raise ILIOError(error_raised) from e
        finally:
            self._lock.release()

    def _read_raw(self, reg: CanopenRegister) -> bytes:  # type: ignore [override]
        try:
            self._lock.acquire()
            value = self.__node.sdo.upload(reg.idx, reg.subidx)
        except Exception as e:
            logger.error("Failed reading %s. Exception: %s", str(reg.identifier), e)
            error_raised = f"Error reading {reg.identifier}"
            raise ILIOError(error_raised)
        finally:
            self._lock.release()
        if not isinstance(value, bytes):
            return b""
        return value

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

    def _on_emcy(self, emergency_msg: EmcyError) -> None:
        """Receive an emergency message from canopen and transform it to a CanopenEmergencyMessage.

        Afterward, send the CanopenEmergencyMessage to all the subscribed callbacks.

        Args:
            emergency_msg: The EmcyError instance.

        """
        emergency_message = CanopenEmergencyMessage(self, emergency_msg)
        logger.warning(f"Emergency message received from node {self.target}: {emergency_message}")
        for callback in self.__emcy_observers:
            callback(emergency_message)

    def _change_sdo_timeout(self, value: float) -> None:
        """Changes the SDO timeout of the node."""
        self.__node.sdo.RESPONSE_TIMEOUT = value

    @contextlib.contextmanager
    def _minimum_sdo_timeout(self, value: float) -> Iterator[None]:
        """Context manager to ensure a minimum SDO timeout for the node.

        This context manager will only increase the current SDO timeout; it will
        never decrease it. If the existing timeout is already greater than the
        requested ``value``, no change is made. When the context exits, the
        original timeout is always restored.

        Args:
            value: Minimum SDO timeout to enforce while inside the context.
        """
        old_timeout = self.__node.sdo.RESPONSE_TIMEOUT

        if old_timeout > value:
            # The current timeout is already higher than the requested one
            yield
            return

        # Temporarily change the SDO timeout
        try:
            # Apply the temporary timeout
            self._change_sdo_timeout(value)
            yield
        finally:
            # Always roll back to the old timeout
            self._change_sdo_timeout(old_timeout)

    def _is_register_valid_for_configuration_file(self, register: Register) -> bool:
        is_register_valid = super()._is_register_valid_for_configuration_file(register)
        if not is_register_valid:
            return is_register_valid
        # Exclude the RxPDO and TxPDO related registers
        # Check INGK-980
        return not (
            register.identifier is not None
            and register.identifier.startswith(("CIA301_COMMS_TPDO", "CIA301_COMMS_RPDO"))
        )

    def _adapt_configuration_file_storage_value(
        self,
        configuration_file: ConfigurationFile,
        config_register: ConfigRegister,
        target_register: Register,
    ) -> bytes:
        """Adapt storage value to the current servo.

        If the register is node ID dependent, the value will be adjusted
        according to the servo node ID.

        If the XCF `Register` contains a `data` attribute it will be preferred
        and returned as-is (bytes). Otherwise, the `storage` attribute will be
        converted to bytes using the provided `target_register.dtype`

        Args:
            configuration_file: Configuration file instance.
            config_register: Configuration file register instance.
            target_register: Target register instance.

        Raises:
            ValueError: If the value is not compatible with the register dtype.

        Returns:
            Adapted storage value as bytes.
        """
        data = super()._adapt_configuration_file_storage_value(
            configuration_file, config_register, target_register
        )

        reg_dtype = target_register.dtype

        if (
            configuration_file.device.node_id is not None
            and target_register is not None
            and isinstance(target_register, CanopenRegister)
            and reg_dtype != RegDtype.STR
            and target_register.is_node_id_dependent
        ):
            # Convert bytes to value
            value = convert_bytes_to_dtype(data, reg_dtype)
            if not isinstance(value, (int, float)):
                raise ValueError(
                    f"Illegal value for register with ID {config_register.uid}"
                    f" and dtype {target_register.dtype}: {config_register.storage}"
                )

            # Adjust value according to node ID
            value = value - configuration_file.device.node_id + int(self.target)
            # Convert value back to bytes
            data = convert_dtype_to_bytes(
                value,
                reg_dtype,
            )

        return data

    @property
    def node(self) -> canopen.RemoteNode:
        """Remote node of the servo."""
        return self.__node

    @node.setter
    def node(self, node: canopen.RemoteNode) -> None:
        """Remote node of the servo."""
        self.__node = node
