import ingenialogger

from ingenialink.dictionary import Interface
from ingenialink.ethernet.servo import EthernetServo

logger = ingenialogger.get_logger(__name__)


class VirtualServo(EthernetServo):
    """Servo object for all the virtual drive functionalities."""

    interface = Interface.VIRTUAL
