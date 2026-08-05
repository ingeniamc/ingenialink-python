"""Shared TSN servo behavior."""

from abc import ABC

from ingenialink.enums.register import ByteOrder
from ingenialink.servo import Servo


class TSNServoBase(Servo, ABC):
    """Declaration of the base TSN servo behavior."""

    _REGISTER_BYTE_ORDER: ByteOrder = ByteOrder.BIG
