from abc import ABC

from ingenialink.servo import CanopenServoBase


class VirtualCanopenServo(CanopenServoBase, ABC):
    """Base class for virtual CANopen servo implementations."""
