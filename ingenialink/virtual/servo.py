import ingenialogger

from ingenialink.ethernet.servo import EthernetServo
from ingenialink.virtual.dictionary import VirtualDictionary

logger = ingenialogger.get_logger(__name__)


class VirtualServo(EthernetServo):
    """Servo object for all the virtual drive functionalities."""

    DICTIONARY_CLASS = VirtualDictionary
