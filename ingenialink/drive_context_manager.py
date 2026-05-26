from collections import OrderedDict
from collections.abc import Container
from typing import TYPE_CHECKING, Optional, Union, cast

from ingenialogger import get_logger

from ingenialink.dictionary import CanOpenObject
from ingenialink.enums.register import RegAccess
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.exceptions import ILIOError
from ingenialink.register import Register
from ingenialink.servo import RegisterAccessOperation, Servo
from ingenialink.utils._utils import REG_VALUE

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


class DriveRegistersState:
    """Class to represent an immutable state of the drive registers."""

    def __init__(self, values: OrderedDict[Register, REG_VALUE]) -> None:
        """Initialize with an ordered mapping of registers to their values.

        Args:
            values: Ordered mapping from ``Register`` objects to their read values.
        """
        self._values = values

    @classmethod
    def from_hardware(
        cls,
        servo: "Servo",
        axis: Optional[int] = None,
        ignore_uids: Container[str] = frozenset(),
        read_max_attempts: int = 2,
    ) -> "DriveRegistersState":
        """Read current register values from a servo and return an immutable snapshot.

        Args:
            servo: The servo to read registers from.
            axis: If given, only read registers for this axis (subnode).
                When ``None``, all registers from every subnode are read.
            ignore_uids: Register UIDs to skip.
            read_max_attempts: Number of read attempts per register before
                giving up and skipping it.

        Returns:
            A new ``DriveRegistersState`` containing the successfully read values.
        """
        register_values: OrderedDict[Register, REG_VALUE] = OrderedDict()

        registers_iter = (
            servo.dictionary.all_registers()
            if axis is None
            else servo.dictionary.registers(axis).values()
        )

        for register in registers_iter:
            if register.identifier in ignore_uids:
                continue

            if register.access in [RegAccess.WO, RegAccess.RO]:
                continue

            for attempt in range(1, read_max_attempts + 1):
                try:
                    register_values[register] = servo.read(register)
                    break
                except ILIOError as e:
                    message = (
                        f"{e}\n"
                        f"An exception happened while trying to read "
                        f"{register.identifier} from {axis=} "
                        f"attempt ({attempt}/{read_max_attempts})\n "
                    )

                    if attempt < read_max_attempts:
                        logger.warning(f"{message}, \n trying again...")
                    else:
                        logger.error(f"{message}, \n Skipping this register")
                        break

        return cls(register_values)

    def to_tuple_dict(self) -> OrderedDict[tuple[int, str], REG_VALUE]:
        """Convert to an OrderedDict keyed by (subnode, uid) tuples.

        Returns:
            OrderedDict mapping (subnode, uid) to register value.
        """
        return OrderedDict(
            ((reg.subnode, cast("str", reg.identifier)), val) for reg, val in self._values.items()
        )


class DriveRegistersSession:
    """Stateful tracker that monitors register changes against a baseline.

    Subscribes to servo register-update callbacks to record which registers have
    been modified and their new values. ``start()`` / ``stop()`` control the
    callback subscription.

    Args:
        servo: The servo whose register updates are tracked.
        baseline: The immutable snapshot used as the reference state.
        do_not_restore_registers: UIDs that should be ignored by the tracker.
    """

    def __init__(
        self,
        servo: Servo,
        baseline: DriveRegistersState,
        do_not_restore_registers: set[str],
    ) -> None:
        self.servo = servo
        self.baseline = baseline
        self._do_not_restore_registers = do_not_restore_registers
        self.changes: OrderedDict[Register, REG_VALUE] = OrderedDict()

    def to_tuple_dict(self) -> OrderedDict[tuple[int, str], REG_VALUE]:
        """Convert changes to an OrderedDict keyed by ``(subnode, uid)`` tuples.

        Returns:
            OrderedDict mapping ``(subnode, uid)`` to the changed register value.
        """
        return OrderedDict(
            ((reg.subnode, cast("str", reg.identifier)), val) for reg, val in self.changes.items()
        )

    def _register_update_callback(
        self,
        servo: Servo,  # noqa: ARG002
        register: Register,
        value: REG_VALUE,
    ) -> None:
        """Record a register write if it differs from the baseline."""
        uid: str = cast("str", register.identifier)
        if register.access in [RegAccess.WO, RegAccess.RO]:
            return
        if uid in self._do_not_restore_registers:
            return
        if register not in self.baseline._values:
            return

        if register in self.changes:
            previous_value = self.changes[register]
        else:
            previous_value = self.baseline._values[register]
        current_value = value if value is not None else previous_value
        if current_value == previous_value:
            return
        self.changes[register] = current_value
        logger.debug(f"{id(self)}: {uid=} changed from {previous_value!r} to {current_value!r}")

    def start(self) -> None:
        """Subscribe the tracking callback to the servo."""
        self.servo.register_update_subscribe(self._register_update_callback)

    def stop(self) -> None:
        """Unsubscribe the tracking callback from the servo."""
        self.servo.register_update_unsubscribe(self._register_update_callback)


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
        self._axis = axis

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

        self._baseline: Optional[DriveRegistersState] = None

        self._session: Optional[DriveRegistersSession] = None

        self._original_canopen_object_values: dict[CanOpenObject, bytes] = {}

        self._objects_changed: dict[CanOpenObject, bytes] = {}

    @property
    def _registers_changed(self) -> OrderedDict[tuple[int, str], REG_VALUE]:
        """Alias for backward compatibility — delegates to the session."""
        if self._session is None:
            return OrderedDict()
        return self._session.to_tuple_dict()

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
            if self._session is None:
                return
            self._session._register_update_callback(servo=servo, register=register, value=value)
            return

        # Store the object as changed (actual value will be determined during restoration)
        self._objects_changed[obj] = b""  # Placeholder, actual restore uses original value

        logger.debug(f"{id(self)}: Object {obj.uid} changed using complete access to {value!r}.")

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
        self._baseline = DriveRegistersState.from_hardware(
            self.drive, axis=self._axis, ignore_uids=self._do_not_restore_registers
        )
        self._session = DriveRegistersSession(
            servo=self.drive,
            baseline=self._baseline,
            do_not_restore_registers=self._do_not_restore_registers,
        )
        self._original_canopen_object_values = self._store_objects_data()
        self._session.start()
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

        assert self._session is not None
        assert self._baseline is not None

        # Temporarily unsubscribe from callbacks to avoid re-populating tracking during restoration
        self._session.stop()
        self.drive.register_update_complete_access_unsubscribe(self._complete_access_callback)

        try:
            if restore_registers:
                # Clear the current tracking
                self._session.changes.clear()
                # Re-read current register values and restore any differences
                current_register_values = DriveRegistersState.from_hardware(
                    self.drive, axis=self._axis, ignore_uids=self._do_not_restore_registers
                ).to_tuple_dict()
                self._restore_register_data(
                    original_values=self._baseline.to_tuple_dict(),
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
            self._session.start()
            self.drive.register_update_complete_access_subscribe(self._complete_access_callback)

    def __exit__(self, exc_type, exc_value, traceback) -> None:  # type: ignore [no-untyped-def]
        """Unsubscribes from register updates and restores the drive values."""
        assert self._session is not None
        assert self._baseline is not None
        self._session.stop()
        self.drive.register_update_complete_access_unsubscribe(self._complete_access_callback)
        self._restore_register_data(
            original_values=self._baseline.to_tuple_dict(),
            changed_values=self._session.to_tuple_dict(),
            force_restore=False,
        )
        self._restore_objects_data(
            original_values=self._original_canopen_object_values,
            changed_values=self._objects_changed,
        )
