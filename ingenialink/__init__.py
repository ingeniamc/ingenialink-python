from ingenialink.enums.register import RegAccess, RegDtype, RegPhy
from ingenialink.enums.servo import (
    ServoFlags,
    ServoMode,
    ServoState,
    ServoUnitsAcc,
    ServoUnitsPos,
    ServoUnitsTorque,
    ServoUnitsVel,
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
from .network import EepromFileFormat, NetDevEvt, NetProt, NetState, NetTransProt, Network

# WARNING: Deprecated aliases
NET_PROT = NetProt
NET_STATE = NetState
NET_DEV_EVT = NetDevEvt
EEPROM_FILE_FORMAT = EepromFileFormat
NET_TRANS_PROT = NetTransProt
REG_DTYPE = RegDtype
REG_ACCESS = RegAccess
REG_PHY = RegPhy
SERVO_STATE = ServoState
SERVO_FLAGS = ServoFlags
SERVO_MODE = ServoMode
SERVO_UNITS_TORQUE = ServoUnitsTorque
SERVO_UNITS_POS = ServoUnitsPos
SERVO_UNITS_VEL = ServoUnitsVel
SERVO_UNITS_ACC = ServoUnitsAcc

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
    "SERVO_STATE",  # WARNING: deprecated
    "ServoState",
    "SERVO_FLAGS",  # WARNING: deprecated
    "ServoFlags",
    "SERVO_MODE",  # WARNING: deprecated
    "ServoMode",
    "SERVO_UNITS_TORQUE",  # WARNING: deprecated
    "ServoUnitsTorque",
    "SERVO_UNITS_POS",  # WARNING: deprecated
    "ServoUnitsPos",
    "SERVO_UNITS_VEL",  # WARNING: deprecated
    "ServoUnitsVel",
    "SERVO_UNITS_ACC",  # WARNING: deprecated
    "ServoUnitsAcc",
    "Network",
    "Servo",
    "REG_DTYPE",  # WARNING: deprecated
    "RegDtype",
    "REG_ACCESS",  # WARNING: deprecated
    "RegAccess",
    "REG_PHY",  # WARNING: deprecated
    "RegPhy",
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
