from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ingenialink.ethercat.servo import EthercatServo


@dataclass
class EthercatSlaveGroup:
    """Connected EtherCAT servos assigned to a PySOEM process-data group."""

    servos: tuple[EthercatServo, ...]
    group_id: int | None

    def __init__(self, servos: Iterable[EthercatServo], group_id: int | None = None) -> None:
        """Create a group from servo references with unique slave IDs.

        Args:
            servos: Connected EtherCAT servos included in the group.
            group_id: PySOEM process-data group number. If omitted, the network chooses it.

        Raises:
            ValueError: If multiple servos have the same slave ID.
        """
        servo_members = tuple(servos)
        slave_ids = [servo.slave_id for servo in servo_members]
        if len(slave_ids) != len(set(slave_ids)):
            raise ValueError("An EthercatSlaveGroup cannot contain duplicate slaves.")
        self.servos = servo_members
        self.group_id = group_id

    @property
    def slave_ids(self) -> frozenset[int]:
        """The slave IDs derived from the group's servo members."""
        return frozenset(servo.slave_id for servo in self.servos)
