from .network import NetworkMonitor, NET_PROT, \
    NET_STATE, NET_DEV_EVT, NET_TRANS_PROT
from .servo import SERVO_STATE, SERVO_FLAGS, SERVO_MODE, \
    SERVO_UNITS_TORQUE, SERVO_UNITS_POS, SERVO_UNITS_VEL, SERVO_UNITS_ACC
from .monitor import Monitor, MONITOR_TRIGGER

from .ipb.network import IPBNetwork
from .ipb.register import IPBRegister
from .ipb.servo import IPBServo
from .ipb.poller import IPBPoller
from .ipb.register import IPBRegister, REG_DTYPE, REG_ACCESS, REG_PHY
from .ipb.dictionary import IPBDictionary

from .canopen.servo import CanopenServo
from .canopen.network import CanopenNetwork, CAN_DEVICE, CAN_DEVICE, \
    CAN_BAUDRATE, CAN_BIT_TIMMING
from .canopen.poller import CanopenPoller
from .canopen.register import CanopenRegister
from .canopen.dictionary import CanopenDictionary

from ingenialink.utils.errors import err_ipb_last

from ._ingenialink import lib
from ingenialink.utils._utils import pstr

__all__ = ['IPBNetwork', 'NetworkMonitor',
           'NET_PROT', 'NET_DEV_EVT', 'NET_STATE', 'NET_TRANS_PROT',
           'IPBServo', 'SERVO_STATE', 'SERVO_FLAGS', 'SERVO_MODE',
           'SERVO_UNITS_TORQUE', 'SERVO_UNITS_POS', 'SERVO_UNITS_VEL',
           'SERVO_UNITS_ACC',
           'IPBDictionary', 'IPBRegister', 'REG_DTYPE', 'REG_ACCESS', 'REG_PHY',
           'Monitor', 'MONITOR_TRIGGER', 'IPBPoller',
           'CanopenNetwork', 'CAN_DEVICE', 'CAN_BAUDRATE', 'CAN_BIT_TIMMING',
           'CanopenServo', 'CanopenPoller', 'CanopenRegister', 'CanopenDictionary',
           'err_ipb_last']

__version__ = '6.0.0'

try:
    __ingenialink_C_version__ = pstr(lib.il_version())
except Exception as e:
    __ingenialink_C_version__ = '-'
