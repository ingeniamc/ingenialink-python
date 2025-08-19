from collections import OrderedDict
from typing import Optional, Union, cast

from ingenialogger import get_logger

from ingenialink.enums.register import RegAccess
from ingenialink.exceptions import ILEcatStateError, ILIOError
from ingenialink.pdo import PDOServo
from ingenialink.register import Register
from ingenialink.servo import Servo

logger = get_logger(__name__)

# These registers cannot be restored in whatever order, if
# they have been altered, just restore the rpdo and tpdo maps
_PDO_RPDO_MAP_REGISTER_UID = "ETG_COMMS_RPDO_"
_PDO_TPDO_MAP_REGISTER_UID = "ETG_COMMS_TPDO_"


class DriveContextManager:
    """Context used to make modifications in the drive.

    Once the modifications are not needed anymore, the drive values will be restored.
    """

    def __init__(
        self,
        servo: Servo,
        axis: Optional[int] = None,
        do_not_restore_registers: Optional[list[str]] = None,
    ) -> None:
        """Initializes the registers that shouldn't be stored.

        Args:
            servo: servo.
            axis: axis to store/restore registers. If not specified, all axis will be
            stored/restored. Defaults to None.
            do_not_restore_registers: list of registers that should not be stored/restored.
                Defaults to [].
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
        ])

        self._original_register_values: dict[int, dict[str, Union[int, float, str, bytes]]] = {}
        self._registers_changed: OrderedDict[tuple[int, str], Union[int, float, str, bytes]] = (
            OrderedDict()
        )

        # If registers that contain the prefixes defined in _PDO_MAP_REGISTERS_UID
        # present a change, do not restore the exact same value because there is an
        # order that must be followed for that, just restore the whole mapping
        self._reset_rpdo_mapping: bool = False
        self._reset_tpdo_mapping: bool = False

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

        dict_key = (register.subnode, uid)

        # Check if the new value is different from the previous one
        if dict_key in self._registers_changed:
            previous_value = self._registers_changed[dict_key]
        else:
            previous_value = self._original_register_values[register.subnode][uid]
        if value == previous_value:
            return

        # Reset the whole rpdo/tpdo mapping if needed
        if _PDO_RPDO_MAP_REGISTER_UID in uid:
            logger.info(
                f"{id(self)}: {uid=} has been changed, will reset rpdo mapping on context exit"
            )
            self._reset_rpdo_mapping = True
            return
        if _PDO_TPDO_MAP_REGISTER_UID in uid:
            logger.info(
                f"{id(self)}: {uid=} has been changed, will reset tpdo mapping on context exit"
            )
            self._reset_tpdo_mapping = True
            return

        self._registers_changed[dict_key] = value
        logger.info(f"{id(self)}: {uid=} changed from {previous_value!r} to {value!r}")

    def _store_register_data(self) -> None:
        """Saves the value of all registers."""
        axes = list(self.drive.dictionary.subnodes) if self._axis is None else [self._axis]
        for axis in axes:
            self._original_register_values[axis] = {}
            for uid, register in self.drive.dictionary.registers(subnode=axis).items():
                if register.identifier in self._do_not_restore_registers:
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
                self._original_register_values[axis][uid] = register_value

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
                self.drive.write(uid, restore_value, subnode=axis)
            except Exception as e:
                logger.error(
                    f"{id(self)}: {uid} failed to restore value={current_value!r} "
                    f"to {restore_value!r} with exception '{e}', trying again..."
                )
                self.drive.write(uid, restore_value, subnode=axis)
            restored_registers[axis].append(uid)

        if not isinstance(self.drive, PDOServo):
            return

        # Drive must be in pre-operational state to reset the PDO mapping
        # https://novantamotion.atlassian.net/browse/INGK-1160
        if self._reset_tpdo_mapping or self._reset_rpdo_mapping:
            try:
                self.drive.check_servo_is_in_preoperational_state()
            except ILEcatStateError:
                logger.warning(
                    "Cannot reset rpdo/tpdo mapping, drive must be in pre-operational state"
                )
                return

        if self._reset_tpdo_mapping:
            logger.warning(f"{id(self)}: Will reset tpdo mapping")
            self.drive.reset_tpdo_mapping()
        if self._reset_rpdo_mapping:
            logger.warning(f"{id(self)}: Will reset rpdo mapping")
            self.drive.reset_rpdo_mapping()

    def __enter__(self) -> None:
        """Subscribes to register update callbacks and saves the drive values."""
        self._store_register_data()
        self.drive.register_update_subscribe(self._register_update_callback)

    def __exit__(self, exc_type, exc_value, traceback) -> None:  # type: ignore [no-untyped-def]
        """Unsubscribes from register updates and restores the drive values."""
        self.drive.register_update_unsubscribe(self._register_update_callback)
        self._restore_register_data()
