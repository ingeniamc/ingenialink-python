from abc import ABC

from ingenialink.servo import EthercatServoBase


class VirtualEthercatServo(EthercatServoBase, ABC):
    """Base class for virtual EtherCAT servo implementations."""
