import warnings
from typing import Any

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
from .canopen.network import CanBaudrate, CanDevice, CanopenNetwork
from .canopen.register import CanopenRegister
from .canopen.servo import CanopenServo
from .ethercat.network import EthercatNetwork
from .ethernet.network import EthernetNetwork
from .ethernet.servo import EthernetServo
from .network import NetDevEvt, NetProt, NetState, Network

__all__ = [
    "NetProt",
    "NetDevEvt",
    "NetState",
    "ServoState",
    "ServoFlags",
    "ServoMode",
    "ServoUnitsTorque",
    "ServoUnitsPos",
    "ServoUnitsVel",
    "ServoUnitsAcc",
    "Network",
    "Servo",
    "RegDtype",
    "RegAccess",
    "RegPhy",
    "EthercatNetwork",
    "EthernetServo",
    "EthernetNetwork",
    "CanopenNetwork",
    "CanDevice",
    "CanBaudrate",
    "CanopenServo",
    "CanopenRegister",
    "Poller",
    "CanopenDictionaryV2",
]


# WARNING: Deprecated aliases
_DEPRECATED = {
    "NET_PROT": "NetProt",
    "NET_STATE": "NetState",
    "NET_DEV_EVT": "NetDevEvt",
    "EEPROM_FILE_FORMAT": "EepromFileFormat",
    "NET_TRANS_PROT": "NetTransProt",
    "REG_DTYPE": "RegDtype",
    "REG_ACCESS": "RegAccess",
    "REG_PHY": "RegPhy",
    "SERVO_STATE": "ServoState",
    "SERVO_FLAGS": "ServoFlags",
    "SERVO_MODE": "ServoMode",
    "SERVO_UNITS_TORQUE": "ServoUnitsTorque",
    "SERVO_UNITS_POS": "ServoUnitsPos",
    "SERVO_UNITS_VEL": "ServoUnitsVel",
    "SERVO_UNITS_ACC": "ServoUnitsAcc",
    "CAN_DEVICE": "CanDevice",
    "CAN_BAUDRATE": "CanBaudrate",
}


def __getattr__(name: str) -> Any:
    if name in _DEPRECATED:
        warnings.warn(
            f"{name} is deprecated, use {_DEPRECATED[name]} instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return globals()[_DEPRECATED[name]]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__version__ = "7.4.0"
