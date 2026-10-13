from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ingenialink.ethercat.servo import EthercatServo


@dataclass(frozen=True)
class EthercatSlaveGroup:
    """An immutable selection of connected EtherCAT servos."""

    servos: tuple[EthercatServo, ...]

    def __init__(self, servos: Iterable[EthercatServo]) -> None:
        """Create a group from servo references with unique slave IDs.

        Args:
            servos: Connected EtherCAT servos included in the group.

        Raises:
            ValueError: If multiple servos have the same slave ID.
        """
        servo_members = tuple(servos)
        slave_ids = [servo.slave_id for servo in servo_members]
        if len(slave_ids) != len(set(slave_ids)):
            raise ValueError("An EthercatSlaveGroup cannot contain duplicate slaves.")
        object.__setattr__(self, "servos", servo_members)

    @property
    def slave_ids(self) -> frozenset[int]:
        """The slave IDs derived from the group's servo members."""
        return frozenset(servo.slave_id for servo in self.servos)
