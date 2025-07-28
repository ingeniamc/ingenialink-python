import warnings
from typing import Any

from ingenialink.enums.register import RegAccess, RegDtype, RegPhy
from ingenialink.enums.servo import (
    ServoMode,
    ServoState,
    ServoUnitsAcc,
    ServoUnitsPos,
    ServoUnitsTorque,
    ServoUnitsVel,
)
from ingenialink.poller import Poller
from ingenialink.servo import Servo

# Canopen
from .canopen.dictionary import CanopenDictionary, CanopenDictionaryV2, CanopenDictionaryV3
from .canopen.network import CanBaudrate, CanDevice, CanopenNetwork
from .canopen.register import CanopenRegister
from .canopen.servo import CanopenServo
from .dictionary import Dictionary, DictionaryV2, DictionaryV3

# Ethercat
from .ethercat.dictionary import EthercatDictionary, EthercatDictionaryV2, EthercatDictionaryV3
from .ethercat.network import EthercatNetwork, GilReleaseConfig
from .ethercat.register import EthercatRegister
from .ethercat.servo import EthercatServo

# Ethernet
from .ethernet.dictionary import EthernetDictionary, EthernetDictionaryV2, EthernetDictionaryV3
from .ethernet.network import EthernetNetwork
from .ethernet.register import EthernetRegister
from .ethernet.servo import EthernetServo

# Generic
from .network import NetDevEvt, NetProt, NetState, Network
from .register import Register

try:
    from ._version import __version__  # noqa: F401
except ModuleNotFoundError:
    __version__ = "development"


__all__ = [
    "__version__",
    "NetProt",
    "NetDevEvt",
    "NetState",
    "ServoState",
    "ServoMode",
    "ServoUnitsTorque",
    "ServoUnitsPos",
    "ServoUnitsVel",
    "ServoUnitsAcc",
    "Register",
    "Network",
    "Servo",
    "Dictionary",
    "DictionaryV2",
    "DictionaryV3",
    "RegDtype",
    "RegAccess",
    "RegPhy",
    "EthercatNetwork",
    "EthercatServo",
    "EthercatDictionary",
    "EthercatDictionaryV2",
    "EthercatDictionaryV3",
    "EthercatRegister",
    "GilReleaseConfig",
    "EthernetServo",
    "EthernetDictionary",
    "EthernetDictionaryV2",
    "EthernetDictionaryV3",
    "EthernetRegister",
    "EthernetNetwork",
    "CanopenNetwork",
    "CanopenDictionary",
    "CanopenDictionaryV2",
    "CanopenDictionaryV3",
    "CanDevice",
    "CanBaudrate",
    "CanopenServo",
    "CanopenRegister",
    "Poller",
]


# WARNING: Deprecated aliases
_DEPRECATED = {
    "NET_PROT": "NetProt",
    "NET_STATE": "NetState",
    "NET_DEV_EVT": "NetDevEvt",
    "REG_DTYPE": "RegDtype",
    "REG_ACCESS": "RegAccess",
    "REG_PHY": "RegPhy",
    "SERVO_STATE": "ServoState",
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
