from typing import Optional, Union, cast

from ingenialink.enums.register import RegAccess
from ingenialink.exceptions import ILIOError
from ingenialink.register import Register
from ingenialink.servo import Servo


class DriveContextManager:
    """Context used to make modifications in the drive.

    Once the modifications are not needed anymore, the drive values will be restored.
    """

    def __init__(
        self,
        servo: Servo,
        axis: Optional[int] = None,
    ):
        self.drive = servo
        self._axis: Optional[int] = axis

        self._original_register_values: dict[int, dict[str, Union[int, float, str, bytes]]] = {}
        self._registers_changed: dict[int, dict[str, Union[int, float, str, bytes]]] = {}

    def _register_update_callback(
        self,
        servo: Servo,  # noqa: ARG002
        register: Register,
        value: Union[int, float, str, bytes],
    ) -> None:
        """Saves the register uids that are changed.

        Args:
            alias: servo alias.
            servo: servo.
            register: register.
            value: changed value.
        """
        if register.subnode not in self._registers_changed:
            self._registers_changed[register.subnode] = {}
        self._registers_changed[register.subnode][cast("str", register.identifier)] = value

    def _store_register_data(self) -> None:
        """Saves the value of all registers."""
        drive = self.drive
        axes = list(drive.dictionary.subnodes) if self._axis is None else [self._axis]
        for axis in axes:
            self._original_register_values[axis] = {}
            for uid, register in drive.dictionary.registers(subnode=axis).items():
                if register.access in [RegAccess.WO, RegAccess.RO]:
                    continue
                try:
                    register_value = self.drive.read(uid, subnode=axis)
                except ILIOError:
                    continue
                self._original_register_values[axis][uid] = register_value

    def _restore_register_data(self) -> None:
        """Restores the drive values."""
        for axis, registers in self._registers_changed.items():
            for uid, current_value in registers.items():
                restore_value = self._original_register_values[axis].get(uid, None)
                if restore_value is None or current_value == restore_value:
                    continue
                self.drive.write(uid, restore_value, subnode=axis)

    def __enter__(self) -> None:
        """Subscribes to register update callbacks and saves the drive values."""
        self._store_register_data()
        self.drive.register_update_subscribe(self._register_update_callback)

    def __exit__(self, exc_type, exc_value, traceback) -> None:  # type: ignore [no-untyped-def]
        """Unsubscribes from register updates and restores the drive values."""
        self.drive.register_update_unsubscribe(self._register_update_callback)
        self._restore_register_data()
