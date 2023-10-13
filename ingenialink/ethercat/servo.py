from typing import Optional

from pysoem import CdefSlave
import ingenialogger

from ingenialink.exceptions import ILIOError
from ingenialink.servo import Servo
from ingenialink.canopen.dictionary import CanopenDictionary
from ingenialink.canopen.register import CanopenRegister

logger = ingenialogger.get_logger(__name__)


class EthercatServo(Servo):  # type: ignore
    """Ethercat Servo instance.

    Args:
        slave: Slave to be connected.
        slave_id: Slave ID.
        dictionary_path: Path to the dictionary.
        servo_status_listener: Toggle the listener of the servo for
            its status, errors, faults, etc.

    """

    DICTIONARY_CLASS = CanopenDictionary

    def __init__(
        self,
        slave: CdefSlave,
        slave_id: int,
        dictionary_path: Optional[str] = None,
        servo_status_listener: bool = False,
    ):
        self.__slave = slave
        self.slave_id = slave_id
        super(EthercatServo, self).__init__(slave.name, dictionary_path, servo_status_listener)

    def _read_raw(self, reg: CanopenRegister) -> bytearray:
        self._lock.acquire()
        try:
            value: bytearray = self.__slave.sdo_read(reg.idx, reg.subidx)
        except Exception as e:
            raise ILIOError(f"Error reading {reg.identifier}. Reason: {e}") from e
        finally:
            self._lock.release()
        return value

    def _write_raw(self, reg: CanopenRegister, data: bytes) -> None:
        self._lock.acquire()
        try:
            self.__slave.sdo_write(reg.idx, reg.subidx, data)
        except Exception as e:
            raise ILIOError(f"Error writing {reg.identifier}. Reason: {e}") from e
        finally:
            self._lock.release()

    @property
    def slave(self) -> CdefSlave:
        """Ethercat slave"""
        return self.__slave
