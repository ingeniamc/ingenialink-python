from ingenialink.enums.register import REG_ACCESS, REG_DTYPE, REG_PHY, RegDtype
from ingenialink.enums.servo import (
    SERVO_FLAGS,
    SERVO_MODE,
    SERVO_STATE,
    SERVO_UNITS_ACC,
    SERVO_UNITS_POS,
    SERVO_UNITS_TORQUE,
    SERVO_UNITS_VEL,
)
from ingenialink.poller import Poller
from ingenialink.servo import Servo

from .canopen.dictionary import CanopenDictionaryV2
from .canopen.network import CAN_BAUDRATE, CAN_DEVICE, CanopenNetwork
from .canopen.register import CanopenRegister
from .canopen.servo import CanopenServo
from .ethercat.network import EthercatNetwork
from .ethernet.network import EthernetNetwork
from .ethernet.servo import EthernetServo
from .network import (
    EEPROM_FILE_FORMAT,
    NET_DEV_EVT,
    NET_PROT,
    NET_STATE,
    NET_TRANS_PROT,
    EepromFileFormat,
    NetDevEvt,
    NetProt,
    NetState,
    NetTransProt,
    Network,
)

__all__ = [
    "EEPROM_FILE_FORMAT",  # WARNING: deprecated
    "EepromFileFormat",
    "NET_PROT",  # WARNING: deprecated
    "NetProt",
    "NET_DEV_EVT",  # WARNING: deprecated
    "NetDevEvt",
    "NET_STATE",  # WARNING: deprecated
    "NetState",
    "NET_TRANS_PROT",  # WARNING: deprecated
    "NetTransProt",
    "SERVO_STATE",
    "SERVO_FLAGS",
    "SERVO_MODE",
    "SERVO_UNITS_TORQUE",
    "SERVO_UNITS_POS",
    "SERVO_UNITS_VEL",
    "SERVO_UNITS_ACC",
    "Network",
    "Servo",
    "REG_DTYPE",  # WARNING: deprecated
    "RegDtype",
    "REG_ACCESS",
    "REG_PHY",
    "EthercatNetwork",
    "EthernetServo",
    "EthernetNetwork",
    "CanopenNetwork",
    "CAN_DEVICE",
    "CAN_BAUDRATE",
    "CanopenServo",
    "CanopenRegister",
    "Poller",
    "CanopenDictionaryV2",
]

__version__ = "7.4.0"
