from collections import OrderedDict
from collections.abc import Callable, Container, Iterable, Iterator, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, NamedTuple, Optional, Union

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


class RestoredEntry(NamedTuple):
    """A register that was successfully restored to its baseline value."""

    register: Register
    value: REG_VALUE


class FailedEntry(NamedTuple):
    """A register that failed to restore after all retry attempts."""

    register: Register
    value: REG_VALUE
    error: Exception


class SkippedEntry(NamedTuple):
    """A register that was skipped during restoration."""

    register: Register
    reason: str


class RestoreResult:
    """Structured result from a register restoration operation.

    Collects which registers were successfully restored, which failed, and
    which were skipped, so callers can log, display, or raise as appropriate
    instead of having the restore method raise on individual failures.
    """

    def __init__(self) -> None:
        self.restored: list[RestoredEntry] = []
        self.failed: list[FailedEntry] = []
        self.skipped: list[SkippedEntry] = []

    @property
    def all_succeeded(self) -> bool:
        """Return ``True`` if no registers failed to restore."""
        return len(self.failed) == 0

    def summary(self) -> str:
        """Return a one-line human-readable summary of the result."""
        parts = [f"Restored: {len(self.restored)}"]
        if self.failed:
            parts.append(f"Failed: {len(self.failed)}")
        if self.skipped:
            parts.append(f"Skipped: {len(self.skipped)}")
        return ", ".join(parts)


# PDO registers
_PDO_RPDO_MAP_REGISTER_UID = "ETG_COMMS_RPDO_"
_PDO_TPDO_MAP_REGISTER_UID = "ETG_COMMS_TPDO_"

# Monitoring and disturbance objects
# In CANopen dictionaries, the uid is "MON_DATA_VALUE" and "DIST_DATA_VALUE"
# In EtherCAT dictionaries, the uid is "MON_DATA" and "DIST_DATA"
_MON_DATA_OBJECT_UID = "MON_DATA"
_DIST_DATA_OBJECT_UID = "DIST_DATA"


class DriveRegistersValue:
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
        ignore_registers: Container[Register] = frozenset(),
        read_max_attempts: int = 2,
    ) -> "DriveRegistersValue":
        """Read current register values from a servo and return an immutable snapshot.

        Args:
            servo: The servo to read registers from.
            axis: If given, only read registers for this axis (subnode).
                When ``None``, all registers from every subnode are read.
            ignore_registers: Register instances to skip.
            read_max_attempts: Number of read attempts per register before
                giving up and skipping it.

        Returns:
            A new ``DriveRegistersValue`` containing the successfully read values.
        """
        register_values: OrderedDict[Register, REG_VALUE] = OrderedDict()

        registers_iter = (
            servo.dictionary.all_registers()
            if axis is None
            else servo.dictionary.registers(axis).values()
        )

        for register in cls.filter_registers(registers_iter, ignore_registers, axis):
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

    def diff(
        self, other: "DriveRegistersValue"
    ) -> OrderedDict[Register, tuple[REG_VALUE, REG_VALUE]]:
        """Compare this state with another and return registers that differ.

        Only registers present in both states are compared.

        Args:
            other: The other state to compare against.

        Returns:
            OrderedDict mapping registers to ``(self_value, other_value)`` for
            registers whose values differ.
        """
        result: OrderedDict[Register, tuple[REG_VALUE, REG_VALUE]] = OrderedDict()
        for register, self_value in self._values.items():
            if register in other._values:
                other_value = other._values[register]
                if self_value != other_value:
                    result[register] = (self_value, other_value)
        return result

    @classmethod
    def from_dict(
        cls,
        data: OrderedDict[Register, REG_VALUE],
        ignore_registers: Container[Register] = frozenset(),
        axis: Optional[int] = None,
    ) -> "DriveRegistersValue":
        """Construct a value snapshot from an existing in-memory mapping.

        This enables building a baseline without hardware I/O, for example
        from an application-level register cache.

        Args:
            data: Ordered mapping from ``Register`` objects to their values.
            ignore_registers: Registers to exclude from the snapshot.
            axis: If given, only include registers with this subnode.
                When ``None``, all subnodes are included.

        Returns:
            A new ``DriveRegistersValue`` wrapping the filtered data.
        """
        return cls(
            OrderedDict(
                (reg, data[reg]) for reg in cls.filter_registers(data, ignore_registers, axis)
            )
        )

    @staticmethod
    def filter_registers(
        registers: Iterable[Register],
        ignore_registers: Container[Register] = frozenset(),
        axis: Optional[int] = None,
    ) -> Iterator[Register]:
        """Yield registers that pass the axis and exclusion filters.

        Args:
            registers: The register iterable to filter.
            ignore_registers: Registers to exclude.
            axis: If given, only yield registers with this subnode.
                When ``None``, all subnodes pass.

        Yields:
            Registers that are not in the exclusion set and match the axis.
        """
        for reg in registers:
            if reg not in ignore_registers and (axis is None or reg.subnode == axis):
                yield reg

    def get(self, register: Register) -> Optional[REG_VALUE]:
        """Look up a single register value from the snapshot.

        Args:
            register: The register to look up.

        Returns:
            The stored value, or ``None`` if the register is not in this snapshot.
        """
        return self._values.get(register)


class DriveRegistersSession:
    """Stateful tracker that monitors register changes against a baseline.

    Subscribes to servo register-update callbacks to record which registers have
    been modified and their new values. ``start()`` / ``stop()`` control the
    callback subscription.

    Args:
        servo: The servo whose register updates are tracked.
        baseline: The immutable snapshot used as the reference state.
        do_not_restore_registers: UIDs that should be ignored by the tracker.
        axis: Axis (subnode) scope.  ``None`` means all axes.
    """

    def __init__(
        self,
        servo: Servo,
        baseline: DriveRegistersValue,
        do_not_restore_registers: Container[Register] = frozenset(),
        axis: Optional[int] = None,
    ) -> None:
        self.servo = servo
        self.baseline = baseline
        self._do_not_restore_registers = do_not_restore_registers
        self._axis = axis
        self._changes: OrderedDict[Register, REG_VALUE] = OrderedDict()

    def _register_update_callback(
        self,
        servo: Servo,  # noqa: ARG002 - required by callback signature, unused here
        register: Register,
        value: REG_VALUE,
    ) -> None:
        """Record a register write if it differs from the baseline."""
        if register.access in [RegAccess.WO, RegAccess.RO]:
            return
        if register in self._do_not_restore_registers:
            return
        if register not in self.baseline._values:
            return

        if register in self._changes:
            previous_value = self._changes[register]
        else:
            previous_value = self.baseline._values[register]
        if value == previous_value:
            return
        self._changes[register] = value
        logger.debug(
            f"{id(self)}: uid={register.identifier!r} changed from {previous_value!r} to {value!r}"
        )

    def current_value(self) -> DriveRegistersValue:
        """Return the current register values: baseline overlaid with tracked changes.

        Returns:
            A new ``DriveRegistersValue`` with baseline values updated by any
            changes recorded so far.
        """
        merged: OrderedDict[Register, REG_VALUE] = OrderedDict(self.baseline._values)
        merged.update(self._changes)
        return DriveRegistersValue(merged)

    @property
    def changes(self) -> Mapping[Register, REG_VALUE]:
        """Read-only view of the tracked register changes."""
        return MappingProxyType(self._changes)

    def _write_with_retry(
        self,
        register: Register,
        value: REG_VALUE,
        result: RestoreResult,
        max_attempts: int = 2,
    ) -> None:
        """Write a register value with retry, recording the outcome in *result*."""
        for attempt in range(1, max_attempts + 1):
            try:
                self.servo.write(register, value)
                result.restored.append(RestoredEntry(register, value))
                return
            except Exception as e:  # noqa: PERF203
                if attempt < max_attempts:
                    logger.error(
                        f"{id(self)}: {register.identifier} failed to restore to "
                        f"{value!r} on axis={register.subnode} with exception '{e}', "
                        f"attempt ({attempt}/{max_attempts})"
                    )
                else:
                    result.failed.append(FailedEntry(register, value, e))

    def restore(self, write_max_attempts: int = 2) -> RestoreResult:
        """Restore tracked changes back to their baseline values.

        Iterates changes in reverse chronological order (undo-stack), writing
        the original baseline value back to hardware for each changed register.

        Args:
            write_max_attempts: Number of write attempts per register before
                recording a failure.

        Returns:
            A ``RestoreResult`` summarising successes, failures, and skips.
        """
        result = RestoreResult()

        for register, current_value in reversed(self._changes.items()):
            baseline_value = self.baseline._values.get(register)
            if baseline_value is None:
                result.skipped.append(SkippedEntry(register, "No baseline value"))
                continue

            if current_value == baseline_value:
                continue

            logger.debug(
                f"Restoring {register.identifier!s} to {baseline_value!r} "
                f"on axis={register.subnode}"
            )
            self._write_with_retry(register, baseline_value, result, write_max_attempts)

        return result

    def force_restore(self, write_max_attempts: int = 2) -> RestoreResult:
        """Force-restore all registers to baseline by re-reading hardware.

        Re-reads all registers via ``DriveRegistersValue.from_hardware()``,
        diffs against the baseline, and restores any that differ.  The tracked
        changes are cleared before reading so subsequent tracking starts fresh.

        Args:
            write_max_attempts: Number of write attempts per register before
                recording a failure.

        Returns:
            A ``RestoreResult`` summarising successes, failures, and skips.
        """
        self._changes.clear()

        current = DriveRegistersValue.from_hardware(
            self.servo,
            axis=self._axis,
            ignore_registers=self._do_not_restore_registers,
        )
        differences = self.baseline.diff(current)

        result = RestoreResult()
        for register, (baseline_value, _current_value) in differences.items():
            logger.debug(
                f"Force restoring {register.identifier!s} to {baseline_value!r} "
                f"on axis={register.subnode}"
            )
            self._write_with_retry(register, baseline_value, result, write_max_attempts)

        return result

    def start(self) -> None:
        """Subscribe the tracking callback to the servo."""
        self.servo.register_update_subscribe(self._register_update_callback)

    def stop(self) -> None:
        """Unsubscribe the tracking callback from the servo."""
        self.servo.register_update_unsubscribe(self._register_update_callback)

    def reset(self) -> None:
        """Clear all tracked changes.

        After calling this, the session behaves as if no register writes
        have occurred since the baseline was established. This clears ``self._changes``
        and re-bases the session from the current tracked state.
        """
        self.baseline = self.current_value()
        self._changes.clear()


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
        baseline: Optional[DriveRegistersValue] = None,
        track_objects: bool = True,
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
            baseline: pre-built register snapshot to use as the baseline state.
                When provided, ``__enter__`` skips the hardware read and uses this
                snapshot directly.  Defaults to None (read from hardware).
            track_objects: whether to read and restore complete-access objects
                (PDO maps, monitoring/disturbance data).  Defaults to True.
                Set to False when only register-level tracking is needed.
        """
        self._drive = servo
        self._axis = axis

        self._do_not_restore_registers: set[Register] = set(
            servo.dictionary.find_registers(
                # User-provided UIDs
                *(do_not_restore_registers or []),
                # Default registers that should never be restored
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
                # PDO mapping registers are restored via complete access, not individually.
                "ETG_COMMS_RPDO_MAP*",
                "ETG_COMMS_TPDO_MAP*",
            )
        )

        # Set the objects that should be read using complete access
        self._complete_access_objects: set[str] = (
            set(complete_access_objects) if isinstance(complete_access_objects, list) else set()
        )

        self._baseline: Optional[DriveRegistersValue] = baseline

        self._track_objects = track_objects

        self._session: Optional[DriveRegistersSession] = None

        self._original_canopen_object_values: dict[CanOpenObject, bytes] = {}

        self._objects_changed: dict[CanOpenObject, bytes] = {}

    @property
    def drive(self) -> Servo:
        """The servo this context manager operates on."""
        return self._drive

    @drive.setter
    def drive(self, servo: Servo) -> None:
        self._drive = servo
        if self._session is not None:
            self._session.servo = servo

    @property
    def _register_update_callback(
        self,
    ) -> Callable[[Servo, Register, REG_VALUE], None]:
        """Alias for backward compatibility; delegates to the session callback.

        Raises:
            RuntimeError: If no active session exists (``__enter__`` not called).
        """
        if self._session is None:
            raise RuntimeError(
                "DriveContextManager has no active session. "
                "Call __enter__() before accessing _register_update_callback."
            )
        return self._session._register_update_callback

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
                raise RuntimeError(
                    "DriveContextManager has no active session. "
                    "Call __enter__() before accessing _complete_access_callback."
                )
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
        if self._baseline is None:
            self._baseline = DriveRegistersValue.from_hardware(
                self.drive, axis=self._axis, ignore_registers=self._do_not_restore_registers
            )
        self._session = DriveRegistersSession(
            servo=self.drive,
            baseline=self._baseline,
            do_not_restore_registers=self._do_not_restore_registers,
            axis=self._axis,
        )
        if self._track_objects:
            self._original_canopen_object_values = self._store_objects_data()
        self._session.start()
        if self._track_objects:
            self.drive.register_update_complete_access_subscribe(self._complete_access_callback)

    def force_restore(self, restore_registers: bool = True, restore_objects: bool = True) -> None:
        """Force restoration of all registers to their original values.

        This method re-reads all registers that were originally stored in __enter__,
        compares them with the original values, and restores any that have changed.
        It ignores the current state of the session's tracked changes and _objects_changed,
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
        if self._track_objects:
            self.drive.register_update_complete_access_unsubscribe(self._complete_access_callback)

        try:
            if restore_registers:
                self._session.force_restore()

            if restore_objects and self._track_objects:
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
            if self._track_objects:
                self.drive.register_update_complete_access_subscribe(self._complete_access_callback)

    def __exit__(self, exc_type, exc_value, traceback) -> None:  # type: ignore [no-untyped-def]
        """Unsubscribes from register updates and restores the drive values."""
        assert self._session is not None
        assert self._baseline is not None
        self._session.stop()
        if self._track_objects:
            self.drive.register_update_complete_access_unsubscribe(self._complete_access_callback)
        self._session.restore()
        if self._track_objects:
            self._restore_objects_data(
                original_values=self._original_canopen_object_values,
                changed_values=self._objects_changed,
            )
