from typing import Optional

import pysoem
from pysoem import CdefSlave
import ingenialogger

from ingenialink.exceptions import ILIOError
from ingenialink.servo import Servo
from ingenialink.ethernet.dictionary import EthernetDictionary
from ingenialink.ethernet.register import EthernetRegister

logger = ingenialogger.get_logger(__name__)


class EthercatServo(Servo):
    """Ethercat Servo instance.

    Args:
        slave_id: Slave ID to be connected.
        dictionary_path: Path to the dictionary
        servo_status_listener: Toggle the listener of the servo for
            its status, errors, faults, etc.

    """

    DICTIONARY_CLASS = EthernetDictionary

    def __init__(
        self,
        slave: CdefSlave,
        dictionary_path: Optional[str] = None,
        servo_status_listener: bool = False,
    ):
        self.__slave = slave
        super(EthercatServo, self).__init__(slave.name, dictionary_path, servo_status_listener)

    def read(self, reg, subnode: int = 1):
        value = super().read(reg, subnode=subnode)
        if isinstance(value, str):
            value = value.replace("\x00", "")
        return value

    def _read_raw(self, reg: EthernetRegister):
        try:
            self._lock.acquire()
            value = self.__slave.sdo_read(0x2000 + reg.address, 0)
        except pysoem.Emergency as e:
            while True:
                try:
                    self.__slave.mbx_receive()
                except pysoem.Emergency:
                    logger.debug("Cleaning emcy message")
                else:
                    break
            logger.error("Failed reading %s. Exception: %s", str(reg.identifier), e)
            value = self.__slave.sdo_read(0x2000 + reg.address, 0)
        except Exception as e:
            logger.error("Failed reading %s. Exception: %s", str(reg.identifier), e)
            error_raised = f"Error reading {reg.identifier}"
            raise ILIOError(error_raised)
        finally:
            self._lock.release()
        return value

    @property
    def slave(self):
        """Ethercat slave"""
        return self.__slave
