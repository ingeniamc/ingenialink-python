import ipaddress

from ingenialink.utils._utils import *
from ingenialink.exceptions import ILError
from ingenialink.constants import PASSWORD_STORE_RESTORE_TCP_IP, \
    MCB_CMD_READ, MCB_CMD_WRITE
from ingenialink.ipb.register import IPBRegister, REG_DTYPE, REG_ACCESS
from ingenialink.ethernet.register import EthernetRegister
from ingenialink.ipb.servo import STORE_COCO_ALL, RESTORE_COCO_ALL
from ingenialink.servo import Servo
from ingenialink.utils.mcb import MCB
from ingenialink.utils._utils import convert_bytes_to_dtype, convert_dtype_to_bytes
from ingenialink.exceptions import ILRegisterNotFoundError

import ingenialogger
logger = ingenialogger.get_logger(__name__)


COMMS_ETH_IP = IPBRegister(
    identifier='', units='', subnode=0, address=0x00A1, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
)
COMMS_ETH_NET_MASK = IPBRegister(
    identifier='', units='', subnode=0, address=0x00A2, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
)
COMMS_ETH_NET_GATEWAY = IPBRegister(
    identifier='', units='', subnode=0, address=0x00A3, cyclic='CONFIG',
    dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
)


class EthernetServo(Servo):
    """Servo object for all the Ethernet slave functionalities.

    Args:
        socket (socket):
        dictionary_path (str): Path to the dictionary.
        servo_status_listener (bool): Toggle the listener of the servo for
            its status, errors, faults, etc.

    """
    def __init__(self, socket,
                 dictionary_path=None, servo_status_listener=False):
        self.socket = socket
        self.ip_address, self.port = self.socket.getpeername()
        super(EthernetServo, self).__init__(self.ip_address)

        #if servo_status_listener:
        #    self.start_status_listener()
        #else:
        #    self.stop_status_listener()

    def store_tcp_ip_parameters(self):
        """Stores the TCP/IP values. Affects IP address,
        subnet mask and gateway"""
        self.write(reg=STORE_COCO_ALL,
                   data=PASSWORD_STORE_RESTORE_TCP_IP,
                   subnode=0)
        logger.info('Store TCP/IP successfully done.')

    def restore_tcp_ip_parameters(self):
        """Restores the TCP/IP values back to default. Affects
        IP address, subnet mask and gateway"""
        self.write(reg=RESTORE_COCO_ALL,
                   data=PASSWORD_STORE_RESTORE_TCP_IP,
                   subnode=0)
        logger.info('Restore TCP/IP successfully done.')

    def change_tcp_ip_parameters(self, ip_address, subnet_mask, gateway):
        """Stores the TCP/IP values. Affects IP address,
        network mask and gateway

        .. note::
            The drive needs a power cycle after this
            in order for the changes to be properly applied.

        Args:
            ip_address (str): IP Address to be changed.
            subnet_mask (str): Subnet mask to be changed.
            gateway (str): Gateway to be changed.

        Raises:
            ValueError: If the drive or gateway IP is not a
            valid IP address.
            ValueError: If the drive IP and gateway IP are not
            on the same network.
            NetmaskValueError: If the subnet_mask is not a valid
            netmask.

        """
        drive_ip = ipaddress.ip_address(ip_address)
        gateway_ip = ipaddress.ip_address(gateway)
        net = ipaddress.IPv4Network(f'{drive_ip}/{subnet_mask}', strict=False)

        if gateway_ip not in net:
            raise ValueError(f'Drive IP {ip_address} and Gateway IP {gateway} '
                             f'are not on the same network.')

        int_ip_address = convert_ip_to_int(ip_address)
        int_subnet_mask = convert_ip_to_int(subnet_mask)
        int_gateway = convert_ip_to_int(gateway)

        self.write(COMMS_ETH_IP, int_ip_address)
        self.write(COMMS_ETH_NET_MASK, int_subnet_mask)
        self.write(COMMS_ETH_NET_GATEWAY, int_gateway)

        try:
            self.store_tcp_ip_parameters()
        except ILError:
            self.store_parameters()

    def write(self, reg, data, subnode=1):
        """Writes data to a register.

        Args:
            reg (IPBRegister, str): Target register to be written.
            data (int, str, float): Data to be written.
            subnode (int): Target axis of the drive.

        """
        _reg = self._get_reg(reg, subnode)
        if isinstance(data, float) and _reg.dtype != REG_DTYPE.FLOAT:
            data = int(data)
        data_bytes = convert_dtype_to_bytes(data, _reg.dtype)
        self._send_mcb_frame(MCB_CMD_WRITE, _reg.idx, _reg.subnode, data_bytes)

    def read(self, reg, subnode=1):
        """Read a register value from servo.

        Args:
            reg (str, Register): Register.
            subnode (int): Target axis of the drive.

        Returns:
            int, float or str: Value stored in the register.
        """
        _reg = self._get_reg(reg, subnode)
        self._send_mcb_frame(MCB_CMD_READ, _reg.idx, _reg.subnode)
        response = self.socket.recv(1024)
        data = MCB.read_mcb_data(_reg.idx, response)
        return convert_bytes_to_dtype(data, _reg.dtype)

    def _get_reg(self, reg, subnode):
        """Validates a register.
        Args:
            reg (EthernetRegister): Targeted register to validate.
            subnode (int): Subnode for the register.
        Returns:
            EthernetRegister: Instance of the desired register from the dictionary.
        Raises:
            ValueError: If the dictionary is not loaded.
            ILWrongRegisterError: If the register has invalid format.
        """
        if isinstance(reg, EthernetRegister):
            return reg

        elif isinstance(reg, str):
            _dict = self.dictionary
            if not _dict:
                raise ValueError('No dictionary loaded')
            if reg not in _dict.registers(subnode):
                raise ILRegisterNotFoundError(f'Register {reg} not found.')
            return _dict.registers(subnode)[reg]
        else:
            raise TypeError('Invalid register')

    def _send_mcb_frame(self, cmd, reg, subnode, data=None):
        frame = MCB.build_mcb_frame(cmd,  subnode, reg, data)
        self.socket.sendall(frame)

    def get_state(self, subnode=1):
        raise NotImplementedError

    def start_status_listener(self):
        raise NotImplementedError

    def stop_status_listener(self):
        raise NotImplementedError

    def subscribe_to_status(self, callback):
        raise NotImplementedError

    def unsubscribe_from_status(self, callback):
        raise NotImplementedError

    def reload_errors(self, dictionary):
        raise NotImplementedError

    def load_configuration(self, config_file, subnode=None):
        raise NotImplementedError

    def save_configuration(self, config_file, subnode=None):
        raise NotImplementedError

    def store_parameters(self, subnode=None):
        raise NotImplementedError

    def restore_parameters(self, subnode=None):
        raise NotImplementedError

    def disable(self, subnode=1):
        raise NotImplementedError

    def enable(self, timeout=2., subnode=1):
        raise NotImplementedError

    def fault_reset(self, subnode=1):
        raise NotImplementedError

    def is_alive(self):
        raise NotImplementedError

