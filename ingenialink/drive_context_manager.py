from collections import OrderedDict
from typing import TYPE_CHECKING, Optional, Union, cast

from ingenialogger import get_logger

from ingenialink.canopen.dictionary import CanopenDictionary
from ingenialink.enums.register import RegAccess
from ingenialink.exceptions import ILEcatStateError, ILIOError
from ingenialink.pdo import PDOServo
from ingenialink.register import Register
from ingenialink.servo import RegisterAccessOperation, Servo

if TYPE_CHECKING:
    from ingenialink.canopen.register import CanopenRegister
    from ingenialink.ethercat.register import EthercatRegister

logger = get_logger(__name__)

# These registers cannot be restored in whatever order, if
# they have been altered, just restore the rpdo and tpdo maps
_PDO_RPDO_MAP_REGISTER_UID = "ETG_COMMS_RPDO_"
_PDO_TPDO_MAP_REGISTER_UID = "ETG_COMMS_TPDO_"

# Monitoring and disturbance objects
# In CANopen dictionaries, the uid is "MON_DATA_VALUE" and "DIST_DATA_VALUE"
# In EtherCAT dictionaries, the uid is "MON_DATA" and "DIST_DATA"
_MON_DATA_OBJECT_UID = "MON_DATA"
_DIST_DATA_OBJECT_UID = "DIST_DATA"


class DriveContextManager:
    """Context used to make modifications in the drive.

    Once the modifications are not needed anymore, the drive values will be restored.
    """

    def __init__(
        self,
        servo: Servo,
        axis: Optional[int] = None,
        do_not_restore_registers: Optional[list[str]] = None,
        complete_access_objects: Optional[list[str]] = None,
    ) -> None:
        """Initializes the registers that shouldn't be stored.

        Args:
            servo: servo.
            axis: axis to store/restore registers. If not specified, all axis will be
            stored/restored. Defaults to None.
            do_not_restore_registers: list of registers that should not be stored/restored.
                Defaults to None.
            complete_access_objects: list of objects that should be read using complete access.
                Objects containing "ETG_COMMS_RPDO_" and "ETG_COMMS_TPDO_" are always read using
                complete access.
            Also, monitoring and disturbance data objects ("MON_DATA" and "DIST_DATA")
                should be read using complete access.
                Defaults to None.
        """
        self.drive = servo
        self._axis: Optional[int] = axis

        self._do_not_restore_registers: set[str] = (
            set(do_not_restore_registers) if isinstance(do_not_restore_registers, list) else set()
        )
        self._do_not_restore_registers.update([
            servo.STORE_COCO_ALL,
            servo.STORE_MOCO_ALL_REGISTERS,
            servo.RESTORE_COCO_ALL,
            servo.RESTORE_MOCO_ALL_REGISTERS,
            # Mac address should not be restored, in certain FW versions the reading of MAC
            # address provides different values each time
            "COMMS_ETH_MAC",
        ])

        # Set the objects that should be read using complete access
        self._complete_access_objects: set[str] = (
            set(complete_access_objects) if isinstance(complete_access_objects, list) else set()
        )

        self._original_register_values: dict[int, dict[str, Union[int, float, str, bytes]]] = {}

        self._original_canopen_object_values: dict[int, dict[str, bytes]] = {}

        # Key: (axis, uid), value
        self._registers_changed: OrderedDict[tuple[int, str], Union[int, float, str, bytes]] = (
            OrderedDict()
        )
        # Key: axis, (object uid, [register uids])
        self._objects_changed: OrderedDict[int, dict[str, list[str]]] = OrderedDict()

        # If registers that contain the prefixes defined in _PDO_MAP_REGISTERS_UID
        # present a change, do not restore the exact same value because there is an
        # order that must be followed for that, just restore the whole mapping
        self._reset_rpdo_mapping: bool = False
        self._reset_tpdo_mapping: bool = False

    def _update_reset_pdo_mapping_flags(self, uid: str) -> bool:
        """Updates the flags that indicate whether the RPDO or TPDO mapping should be reset.

        Args:
            uid: The UID of the register that has been changed.

        Returns:
            True if the register affects the PDO mapping, False otherwise.
        """
        if _PDO_RPDO_MAP_REGISTER_UID in uid:
            logger.debug(
                f"{id(self)}: {uid=} has been changed, will reset rpdo mapping on context exit"
            )
            self._reset_rpdo_mapping = True
            return True
        elif _PDO_TPDO_MAP_REGISTER_UID in uid:
            logger.debug(
                f"{id(self)}: {uid=} has been changed, will reset tpdo mapping on context exit"
            )
            self._reset_tpdo_mapping = True
            return True
        return False

    def _register_update_callback(
        self,
        servo: Servo,  # noqa: ARG002
        register: Register,
        value: Union[int, float, str, bytes],
    ) -> None:
        """Saves the register uids that are changed.

        It will ignore the registers that should not be restored `self._do_not_restore_registers`.

        Args:
            servo: servo.
            register: register.
            value: changed value.
        """
        uid: str = cast("str", register.identifier)
        if register.access in [RegAccess.WO, RegAccess.RO]:
            return
        if uid in self._do_not_restore_registers:
            return
        if uid not in self._original_register_values[register.subnode]:
            return

        # Reset the whole rpdo/tpdo mapping if needed
        reset_pdo_mapping = self._update_reset_pdo_mapping_flags(uid=uid)
        if reset_pdo_mapping:
            return

        # Check if the new value is different from the previous one
        dict_key = (register.subnode, uid)
        if dict_key in self._registers_changed:
            previous_value = self._registers_changed[dict_key]
        previous_value = self._original_register_values[register.subnode][uid]
        current_value = value if value is not None else previous_value
        if current_value == previous_value:
            return
        self._registers_changed[dict_key] = current_value
        logger.debug(f"{id(self)}: {uid=} changed from {previous_value!r} to {current_value!r}")

    def _complete_access_callback(
        self,
        servo: Servo,  # noqa: ARG002
        register: Union["CanopenRegister", "EthercatRegister"],
        value: Union[int, float, str, bytes],
        operation: RegisterAccessOperation,
    ) -> None:
        """Callback for registers changed using complete access.

        Args:
            servo: servo.
            register: register.
            value: changed value.
            operation: read or write depending on the operation performed.

        Raises:
            ValueError: if the register identifier is None.
            ValueError: if the servo dictionary is not a CanopenDictionary instance.
            RuntimeError: if the register has been changed using complete access, but the
                object original value was not stored.
        """
        if operation is RegisterAccessOperation.READ:
            return
        if register.access in [RegAccess.WO, RegAccess.RO]:
            return

        if register.identifier is None:
            raise ValueError("Register identifier cannot be None in complete access.")
        if not isinstance(servo.dictionary, CanopenDictionary):
            raise ValueError("Servo dictionary is not a CanopenDictionary instance.")

        # If the register has been changed using complete access,
        # assume that all the registers in the main object have been changed
        # and should be restored
        obj = servo.dictionary.get_object_by_index(index=register.idx)

        if obj.uid not in self._original_canopen_object_values[register.subnode]:
            raise RuntimeError(
                f"Changed register {register.identifier} using complete access, "
                f"but object {obj.uid} original value not stored."
            )

        if register.subnode not in self._objects_changed:
            self._objects_changed[register.subnode] = {}
        if obj.uid not in self._objects_changed[register.subnode]:
            self._objects_changed[register.subnode][obj.uid] = [register.identifier]
        else:
            self._objects_changed[register.subnode][obj.uid].append(register.identifier)
        self._update_reset_pdo_mapping_flags(uid=register.identifier)
        logger.debug(f"{id(self)}: Object {obj.uid} changed using complete access to {value!r}.")

    def _store_register_data(self) -> None:
        """Saves the value of all registers."""
        axes = list(self.drive.dictionary.subnodes) if self._axis is None else [self._axis]
        for axis in axes:
            self._original_register_values[axis] = {}
            for uid, register in self.drive.dictionary.registers(subnode=axis).items():
                if uid in self._do_not_restore_registers:
                    continue
                if register.access in [RegAccess.WO, RegAccess.RO]:
                    continue
                # These registers will be restored by resetting the PDO mapping
                # or with complete access
                if _PDO_RPDO_MAP_REGISTER_UID in uid or _PDO_TPDO_MAP_REGISTER_UID in uid:
                    continue

                try:
                    register_value = self.drive.read(uid, subnode=axis)
                except ILIOError:
                    continue
                except Exception as e:
                    logger.warning(
                        f"{id(self)}: '{e}' happened while trying to read {uid=} from {axis=}, "
                        "trying again..."
                    )
                    try:
                        register_value = self.drive.read(uid, subnode=axis)
                    except ILIOError:
                        continue
                self._original_register_values[axis][uid] = register_value

    def _store_objects_data(self) -> None:
        axes = list(self.drive.dictionary.subnodes) if self._axis is None else [self._axis]
        for axis in axes:
            self._original_canopen_object_values[axis] = {}
            if axis not in self.drive.dictionary.items:
                continue
            for uid, obj in self.drive.dictionary.items[axis].items():
                # Always read the rpdo/tpdo map objects using complete access
                if (
                    (_PDO_RPDO_MAP_REGISTER_UID not in uid)
                    and (_PDO_TPDO_MAP_REGISTER_UID not in uid)
                    and (_MON_DATA_OBJECT_UID not in uid)
                    and (_DIST_DATA_OBJECT_UID not in uid)
                    and (uid not in self._complete_access_objects)
                ):
                    continue

                try:
                    obj_value = self.drive.read_complete_access(obj, subnode=axis)
                except Exception as e:
                    logger.warning(
                        f"{id(self)}: '{e}' happened while trying to read {uid=} from "
                        f"{axis=}, trying again..."
                    )
                    try:
                        obj_value = self.drive.read_complete_access(obj, subnode=axis)
                    except Exception:
                        continue
                self._original_canopen_object_values[axis][uid] = obj_value

    def _restore_register_data(self) -> None:
        """Restores the drive values."""
        axes = list(self.drive.dictionary.subnodes) if self._axis is None else [self._axis]
        restored_registers: dict[int, list[str]] = {axis: [] for axis in axes}

        for (axis, uid), current_value in reversed(self._registers_changed.items()):
            # No original data for the register
            if uid not in self._original_register_values[axis]:
                continue
            # Register has already been restored with a newer value than the evaluated one
            if uid in restored_registers[axis]:
                continue
            restore_value = self._original_register_values[axis][uid]
            # No change with respect to the original value
            if current_value == restore_value:
                continue

            try:
                logger.debug(f"Restoring {uid=} to {restore_value!r} on {axis=}")
                self.drive.write(uid, restore_value, subnode=axis)
            except Exception as e:
                logger.error(
                    f"{id(self)}: {uid} failed to restore value={current_value!r} "
                    f"to {restore_value!r} with exception '{e}', trying again..."
                )
                self.drive.write(uid, restore_value, subnode=axis)
            restored_registers[axis].append(uid)

    def _restore_objects_data(self) -> None:
        axes = list(self.drive.dictionary.subnodes) if self._axis is None else [self._axis]
        restored_objects: dict[int, list[str]] = {axis: [] for axis in axes}

        for axis, obj in reversed(self._objects_changed.items()):
            for uid, registers in obj.items():
                # Object has already been restored with a newer value than the evaluated one
                if uid in restored_objects[axis]:
                    continue
                restore_value = self._original_canopen_object_values[axis][uid]
                for register in registers:
                    logger.debug(
                        f"Restoring register {register} from object {uid=} on {axis=} "
                        "using complete access."
                    )
                    self.drive.write_complete_access(register, restore_value, subnode=axis)
                restored_objects[axis].append(uid)

        # Drive must be in pre-operational state to reset the PDO mapping
        # https://novantamotion.atlassian.net/browse/INGK-1160
        if isinstance(self.drive, PDOServo) and (
            self._reset_tpdo_mapping or self._reset_rpdo_mapping
        ):
            try:
                self.drive.check_servo_is_in_preoperational_state()
                if self._reset_tpdo_mapping:
                    logger.warning(f"{id(self)}: Will reset tpdo mapping")
                    self.drive.reset_tpdo_mapping()
                if self._reset_rpdo_mapping:
                    logger.warning(f"{id(self)}: Will reset rpdo mapping")
                    self.drive.reset_rpdo_mapping()
            except ILEcatStateError:
                logger.warning(
                    "Cannot reset rpdo/tpdo mapping, drive must be in pre-operational state"
                )

    def __enter__(self) -> None:
        """Subscribes to register update callbacks and saves the drive values."""
        self._store_register_data()
        self._store_objects_data()
        self.drive.register_update_subscribe(self._register_update_callback)
        self.drive.register_update_complete_access_subscribe(self._complete_access_callback)

    def __exit__(self, exc_type, exc_value, traceback) -> None:  # type: ignore [no-untyped-def]
        """Unsubscribes from register updates and restores the drive values."""
        self.drive.register_update_unsubscribe(self._register_update_callback)
        self.drive.register_update_complete_access_unsubscribe(self._complete_access_callback)
        self._restore_register_data()
        self._restore_objects_data()
