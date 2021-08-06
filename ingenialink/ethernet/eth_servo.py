from ..net import Network, NET_PROT, NET_TRANS_PROT
from ..servo import Servo
from ..registers import *
from ..const import SINGLE_AXIS_MINIMUM_SUBNODES
from ..exceptions import *
from ingenialink.utils._utils import cstr, pstr, raise_null, raise_err, to_ms
from .._ingenialink import lib, ffi

import ingenialogger
logger = ingenialogger.get_logger(__name__)

PASSWORD_STORE_ALL = 0x65766173
PASSWORD_RESTORE_ALL = 0x64616F6C

STORE_COCO_ALL = Register(
    identifier='', units='', subnode=0, address=0x06DB, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RW, range=None
)

RESTORE_COCO_ALL = Register(
    identifier='', units='', subnode=0, address=0x06DC, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RW, range=None
)

STORE_MOCO_ALL_REGISTERS = {
    1: Register(
        identifier='', units='', subnode=1, address=0x06DB, cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RW, range=None
    ),
    2: Register(
        identifier='', units='', subnode=2, address=0x06DB, cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RW, range=None
    ),
    3: Register(
        identifier='', units='', subnode=3, address=0x06DB, cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RW, range=None
    )
}


class EthernetServo(Servo):
    def __init__(self, net, target, dictionary, port,
                 communication_protocol, servo_id=None):
        super(EthernetServo, self).__init__(net, servo_id=servo_id, dict_f=dictionary)
        self.__net = net
        self.__target = target
        self.__dictionary = dictionary
        self.__port = port
        self.__communication_protocol = communication_protocol

    def is_alive(self):
        raise NotImplementedError

    def store_parameters(self, subnode=1):
        """ Store all the current parameters of the target subnode.

        Args:
            subnode (int): Subnode of the axis.

        Raises:
            ILError: Invalid subnode.
            ILObjectNotExist: Failed to write to the registers.
        """
        if subnode == 0:
            # Store all
            r = 0
            try:
                self.write(reg=STORE_COCO_ALL,
                           data=PASSWORD_STORE_ALL,
                           subnode=subnode)
                logger.info('Store all successfully done.')
            except Exception as e:
                logger.warning('Store all COCO failed. Trying MOCO...')
                r = -1
            if r < 0:
                if self.__dictionary.subnodes > SINGLE_AXIS_MINIMUM_SUBNODES:
                    # Multiaxis
                    for dict_subnode in self.__dictionary.subnodes:
                        self.write(reg=STORE_MOCO_ALL_REGISTERS[dict_subnode],
                                   data=PASSWORD_STORE_ALL,
                                   subnode=dict_subnode)
                        logger.info('Store axis {} successfully done.'.format(
                            dict_subnode))
                else:
                    # Single axis
                    self.write(reg=STORE_MOCO_ALL_REGISTERS[1],
                               data=PASSWORD_STORE_ALL,
                               subnode=1)
                    logger.info('Store all successfully done.')
        elif subnode > 0:
            # Store axis
            self.write(reg=STORE_MOCO_ALL_REGISTERS[subnode],
                       data=PASSWORD_STORE_ALL,
                       subnode=subnode)
            logger.info('Store axis {} successfully done.'.format(subnode))
        else:
            raise ILError('Invalid subnode.')

    def restore_parameters(self):
        """ Restore all the current parameters of all the slave to default.

        Raises:
            ILError: Invalid subnode.
            ILObjectNotExist: Failed to write to the registers.
        """
        self.write(reg=RESTORE_COCO_ALL,
                   data=PASSWORD_RESTORE_ALL,
                   subnode=0)
        logger.info('Restore all successfully done.')

    @property
    def net(self):
        return self.__net

    @net.setter
    def net(self, value):
        self.__net = value

    @property
    def target(self):
        return self.__target

    @target.setter
    def target(self, value):
        self.__target = value

    @property
    def dictionary(self):
        return self.__dictionary

    @dictionary.setter
    def dictionary(self, value):
        self.__dictionary = value

    @property
    def port(self):
        return self.__port

    @port.setter
    def port(self, value):
        self.__port = value

    @property
    def communication_protocol(self):
        return self.__communication_protocol

    @communication_protocol.setter
    def communication_protocol(self, value):
        self.__communication_protocol = value
