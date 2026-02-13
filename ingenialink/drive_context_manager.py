from collections import OrderedDict
from typing import TYPE_CHECKING, Optional, Union, cast

from ingenialogger import get_logger

from ingenialink.dictionary import CanOpenObject
from ingenialink.enums.register import RegAccess
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.exceptions import ILIOError
from ingenialink.register import Register
from ingenialink.servo import RegisterAccessOperation, Servo

if TYPE_CHECKING:
    from ingenialink.canopen.register import CanopenRegister

logger = get_logger(__name__)

# PDO registers
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
            # Total number of error register should not be restored, only a 0 can be written
            "ETG_ERROR_FIELD",
            "CIA301_COMMS_ERROR_FIELD",
        ])

        # Set the objects that should be read using complete access
        self._complete_access_objects: set[str] = (
            set(complete_access_objects) if isinstance(complete_access_objects, list) else set()
        )

        self._original_register_values: OrderedDict[
            tuple[int, str], Union[int, float, str, bytes]
        ] = OrderedDict()

        self._original_canopen_object_values: dict[CanOpenObject, bytes] = {}

        # Key: (axis, uid), value
        self._registers_changed = OrderedDict[tuple[int, str], Union[int, float, str, bytes]]()

        self._objects_changed: dict[CanOpenObject, bytes] = {}

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
        dict_key = (register.subnode, uid)
        if dict_key not in self._original_register_values:
            return

        # Check if the new value is different from the previous one
        if dict_key in self._registers_changed:
            previous_value = self._registers_changed[dict_key]
        previous_value = self._original_register_values[dict_key]
        current_value = value if value is not None else previous_value
        if current_value == previous_value:
            return
        self._registers_changed[dict_key] = current_value
        logger.debug(f"{id(self)}: {uid=} changed from {previous_value!r} to {current_value!r}")

    def _complete_access_callback(
        self,
        servo: Servo,  # noqa: ARG002
        register: Union["CanopenRegister"],
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
            ValueError: if the servo dictionary is not a CanopenDictionary instance.
            RuntimeError: if the register has been changed using complete access, but the
                object original value was not stored.
        """
        if operation is RegisterAccessOperation.READ:
            return

        # If the register has been changed using complete access,
        # assume that all the registers in the main object have been changed
        # and should be restored
        obj = register.obj
        if obj is None:
            raise ValueError(f"Register {register} has no object associated.")

        # Only restore the object if all its registers allow write access
        # If at least one register is read-only, do not restore the object,
        # restore the register individually instead
        if not obj.all_registers_writable:
            self._register_update_callback(servo=servo, register=register, value=value)
            return

        # Store the object as changed (actual value will be determined during restoration)
        self._objects_changed[obj] = b""  # Placeholder, actual restore uses original value

        logger.debug(f"{id(self)}: Object {obj.uid} changed using complete access to {value!r}.")

    def _store_register_data(self) -> OrderedDict[tuple[int, str], Union[int, float, str, bytes]]:
        """Reads and returns the value of all registers.

        Returns:
            OrderedDict mapping (axis, uid) tuple to register value.
        """
        register_values: OrderedDict[tuple[int, str], Union[int, float, str, bytes]] = OrderedDict()
        axes = list(self.drive.dictionary.subnodes) if self._axis is None else [self._axis]
        for axis in axes:
            for uid, register in self.drive.dictionary.registers(subnode=axis).items():
                if uid in self._do_not_restore_registers:
                    continue
                if register.access in [RegAccess.WO, RegAccess.RO]:
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
                register_values[(axis, uid)] = register_value
        return register_values

    def _store_objects_data(self) -> dict[CanOpenObject, bytes]:
        """Reads and returns complete access objects data.

        Returns:
            Dictionary mapping CanOpenObject to its byte value.
        """
        object_values: dict[CanOpenObject, bytes] = {}
        if not isinstance(self.drive, EthercatServo):
            return object_values
        for obj in self.drive.dictionary.all_objs():
            uid = obj.uid
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
                obj_value = self.drive.read_complete_access(obj)
            except Exception as e:
                logger.warning(
                    f"{id(self)}: '{e}' happened while trying to read {obj}, trying again..."
                )
                try:
                    obj_value = self.drive.read_complete_access(obj)
                except Exception:
                    continue
            object_values[obj] = obj_value
        return object_values

    def _restore_register_data(
        self,
        original_values: OrderedDict[tuple[int, str], Union[int, float, str, bytes]],
        changed_values: OrderedDict[tuple[int, str], Union[int, float, str, bytes]],
        force_restore: bool = False,
    ) -> None:
        """Restores the drive values.

        Args:
            original_values: OrderedDict mapping (axis, uid) to original value.
            changed_values: OrderedDict mapping (axis, uid) to changed value.
            force_restore: If True, registers are being restored by force mode.
        """
        axes = list(self.drive.dictionary.subnodes) if self._axis is None else [self._axis]
        restored_registers: dict[int, list[str]] = {axis: [] for axis in axes}

        for (axis, uid), current_value in reversed(changed_values.items()):
            # No original data for the register
            if (axis, uid) not in original_values:
                continue
            # Register has already been restored with a newer value than the evaluated one
            if uid in restored_registers[axis]:
                continue
            # Skip PDO mapping registers: handled via complete access in _restore_objects_data
            if force_restore and (
                _PDO_RPDO_MAP_REGISTER_UID in uid or _PDO_TPDO_MAP_REGISTER_UID in uid
            ):
                continue
            restore_value = original_values[(axis, uid)]
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

    def _restore_objects_data(
        self,
        original_values: dict[CanOpenObject, bytes],
        changed_values: dict[CanOpenObject, bytes],
    ) -> None:
        """Restores complete access objects.

        Args:
            original_values: Dictionary mapping CanOpenObject to its original byte value.
            changed_values: Dictionary mapping CanOpenObject to changed byte value.
        """
        for obj, current_value in changed_values.items():
            # https://novantamotion.atlassian.net/browse/DRIVSUS-137
            if _MON_DATA_OBJECT_UID in obj.uid or _DIST_DATA_OBJECT_UID in obj.uid:
                continue
            restore_value = original_values.get(obj)
            if restore_value is None:
                logger.warning(
                    f"No original data for the object {obj} to restore. Skipping restoration."
                )
                continue

            # If we have current_value, check if it differs
            if current_value and current_value == restore_value:
                continue

            logger.debug(f"Restoring {obj} using complete access.")
            self.drive.write_complete_access(obj, restore_value)

    def __enter__(self) -> None:
        """Subscribes to register update callbacks and saves the drive values."""
        self._original_register_values = self._store_register_data()
        self._original_canopen_object_values = self._store_objects_data()
        self.drive.register_update_subscribe(self._register_update_callback)
        self.drive.register_update_complete_access_subscribe(self._complete_access_callback)

    def force_restore(self, restore_registers: bool = True, restore_objects: bool = True) -> None:
        """Force restoration of all registers to their original values.

        This method re-reads all registers that were originally stored in __enter__,
        compares them with the original values, and restores any that have changed.
        It ignores the current state of _registers_changed and _objects_changed,
        effectively performing a complete refresh and restoration.

        This is useful when changes have been made outside the context manager's
        tracking (e.g., external modifications to the drive).

        Args:
            restore_registers: If True, restores registers to their original values.
            restore_objects: If True, restores complete access objects to their original values.
        """
        if not restore_registers and not restore_objects:
            return

        # Temporarily unsubscribe from callbacks to avoid re-populating tracking during restoration
        self.drive.register_update_unsubscribe(self._register_update_callback)
        self.drive.register_update_complete_access_unsubscribe(self._complete_access_callback)

        try:
            if restore_registers:
                # Clear the current tracking
                self._registers_changed.clear()
                # Re-read current register values and restore any differences
                current_register_values = self._store_register_data()
                self._restore_register_data(
                    original_values=self._original_register_values,
                    changed_values=current_register_values,
                    force_restore=True,
                )

            if restore_objects:
                # Clear the current tracking
                self._objects_changed.clear()

                # Re-read current object values and restore any differences
                current_object_values = self._store_objects_data()
                self._restore_objects_data(
                    original_values=self._original_canopen_object_values,
                    changed_values=current_object_values,
                )
        finally:
            # Re-subscribe to callbacks
            self.drive.register_update_subscribe(self._register_update_callback)
            self.drive.register_update_complete_access_subscribe(self._complete_access_callback)

    def __exit__(self, exc_type, exc_value, traceback) -> None:  # type: ignore [no-untyped-def]
        """Unsubscribes from register updates and restores the drive values."""
        self.drive.register_update_unsubscribe(self._register_update_callback)
        self.drive.register_update_complete_access_unsubscribe(self._complete_access_callback)
        self._restore_register_data(
            original_values=self._original_register_values,
            changed_values=self._registers_changed,
            force_restore=False,
        )
        self._restore_objects_data(
            original_values=self._original_canopen_object_values,
            changed_values=self._objects_changed,
        )
