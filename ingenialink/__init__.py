from .net import (Network, NetworkMonitor, devices, NET_PROT, NET_STATE,
                  NET_DEV_EVT)
from .servo import (Servo, lucky, SERVO_STATE, SERVO_FLAGS, SERVO_MODE,
                    SERVO_UNITS_TORQUE, SERVO_UNITS_POS, SERVO_UNITS_VEL,
                    SERVO_UNITS_ACC)
from .monitor import Monitor, MONITOR_TRIGGER
from .poller import Poller
from .registers import Register, REG_DTYPE, REG_ACCESS, REG_PHY
from .dict_ import Dictionary
from .dict_labels import LabelsDictionary
from .canopen.servo import CanopenServo
from .canopen.netwrok import CanopenNetwork, CAN_DEVICE
from .canopen.poller import CanopenPoller
from .err import err_ipb_last
from ._ingenialink import lib
from ingenialink.utils._utils import pstr

__all__ = ['Network', 'NetworkMonitor', 'devices', 'NET_PROT', 'NET_DEV_EVT',
           'NET_STATE',
           'Servo', 'lucky', 'SERVO_STATE', 'SERVO_FLAGS', 'SERVO_MODE',
           'SERVO_UNITS_TORQUE', 'SERVO_UNITS_POS', 'SERVO_UNITS_VEL',
           'SERVO_UNITS_ACC',
           'Monitor', 'MONITOR_TRIGGER',
           'Poller',
           'Register', 'REG_DTYPE', 'REG_ACCESS', 'REG_PHY',
           'Dictionary',
           'LabelsDictionary',
           'CanopenNetwork', 'CAN_DEVICE', 'CanopenPoller', 'CanopenServo',
           'err_ipb_last']

__version__ = '5.3.9'

try:
    __ingenialink_C_version__ = pstr(lib.il_version())
except Exception as e:
    __ingenialink_C_version__ = '-'
