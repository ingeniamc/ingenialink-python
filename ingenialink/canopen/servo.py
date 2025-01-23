from typing import Any, Callable, List, Optional, Union

import canopen
import ingenialogger
from canopen.emcy import EmcyError

from ingenialink.canopen.register import CanopenRegister
from ingenialink.constants import CAN_MAX_WRITE_SIZE
from ingenialink.dictionary import Interface
from ingenialink.emcy import EmergencyMessage
from ingenialink.exceptions import ILIOError
from ingenialink.register import Register
from ingenialink.servo import Servo

logger = ingenialogger.get_logger(__name__)

CANOPEN_SDO_RESPONSE_TIMEOUT = 0.3


class CanopenServo(Servo):
    """CANopen Servo instance.

    Args:
        target: Node ID to be connected.
        node: Remote Node of the drive.
        dictionary_path: Path to the dictionary.
        servo_status_listener: Toggle the listener of the servo for
            its status, errors, faults, etc.

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
    ) -> None:
        self.__node = node
        self.__emcy_observers: List[Callable[[EmergencyMessage], None]] = []
        self.__node.emcy.add_callback(self._on_emcy)
        super(CanopenServo, self).__init__(target, dictionary_path, servo_status_listener)

    def read(
        self, reg: Union[str, Register], subnode: int = 1, **kwargs: Any
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

        Raises:
            ILError: Invalid subnode.

        """
        self._change_sdo_timeout(sdo_timeout)
        super().store_parameters(subnode)
        self._change_sdo_timeout(CANOPEN_SDO_RESPONSE_TIMEOUT)

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
        """Receive an emergency message from canopen and transform it to a EmergencyMessage.
        Afterward, send the EmergencyMessage to all the subscribed callbacks.

        Args:
            emergency_msg: The EmcyError instance.

        """
        emergency_message = EmergencyMessage(self, emergency_msg)
        logger.warning(f"Emergency message received from node {self.target}: {emergency_message}")
        for callback in self.__emcy_observers:
            callback(emergency_message)

    def _change_sdo_timeout(self, value: float) -> None:
        """Changes the SDO timeout of the node."""
        self.__node.sdo.RESPONSE_TIMEOUT = value

    def _is_register_valid_for_configuration_file(self, register: Register) -> bool:
        is_register_valid = super()._is_register_valid_for_configuration_file(register)
        if not is_register_valid:
            return is_register_valid
        # Exclude the RxPDO and TxPDO related registers
        # Check INGK-980
        if register.identifier is not None and register.identifier.startswith(
            ("CIA301_COMMS_TPDO", "CIA301_COMMS_RPDO")
        ):
            return False
        return True

    @staticmethod
    def _monitoring_disturbance_map_can_address(address: int, subnode: int) -> int:
        """Map CAN register address to IPB register address."""
        return address - (0x2000 + (0x800 * (subnode - 1)))

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
        ipb_address = self._monitoring_disturbance_map_can_address(address, subnode)
        return super()._monitoring_disturbance_data_to_map_register(
            subnode, ipb_address, dtype, size
        )

    @property
    def node(self) -> canopen.RemoteNode:
        """Remote node of the servo."""
        return self.__node

    @node.setter
    def node(self, node: canopen.RemoteNode) -> None:
        """Remote node of the servo."""
        self.__node = node
