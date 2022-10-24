import ipaddress
import socket

from ingenialink.exceptions import ILError, ILTimeoutError, ILIOError
from ingenialink.constants import PASSWORD_STORE_RESTORE_TCP_IP, \
    MCB_CMD_READ, MCB_CMD_WRITE, ETH_MAX_WRITE_SIZE, ETH_BUF_SIZE
from ingenialink.ethernet.register import EthernetRegister, REG_DTYPE, \
    REG_ACCESS
from ingenialink.servo import Servo
from ingenialink.utils.mcb import MCB
from ingenialink.utils._utils import convert_bytes_to_dtype, \
    convert_dtype_to_bytes, convert_ip_to_int
from ingenialink.ethernet.dictionary import EthernetDictionary

import ingenialogger

logger = ingenialogger.get_logger(__name__)

class EthernetServo(Servo):
    """Servo object for all the Ethernet slave functionalities.

    Args:
        socket (socket):
        dictionary_path (str): Path to the dictionary.
        servo_status_listener (bool): Toggle the listener of the servo for
            its status, errors, faults, etc.

    """
    COMMS_ETH_IP = EthernetRegister(
        identifier='', units='', subnode=0, address=0x00A1, cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    )
    COMMS_ETH_NET_MASK = EthernetRegister(
        identifier='', units='', subnode=0, address=0x00A2, cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    )
    COMMS_ETH_NET_GATEWAY = EthernetRegister(
        identifier='', units='', subnode=0, address=0x00A3, cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    )
    STATUS_WORD_REGISTERS = {
        1: EthernetRegister(
            identifier='', units='', subnode=1, address=0x0011,
            cyclic='CYCLIC_TX', dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
        ),
        2: EthernetRegister(
            identifier='', units='', subnode=2, address=0x0011,
            cyclic='CYCLIC_TX', dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
        ),
        3: EthernetRegister(
            identifier='', units='', subnode=3, address=0x0011,
            cyclic='CYCLIC_TX', dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
        )
    }
    RESTORE_COCO_ALL = EthernetRegister(
        identifier='', units='', subnode=0, address=0x06DC, cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    )
    RESTORE_MOCO_ALL_REGISTERS = {
        1: EthernetRegister(
            identifier='', units='', subnode=1, address=0x06DC,
            cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
        ),
        2: EthernetRegister(
            identifier='', units='', subnode=2, address=0x06DC,
            cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
        ),
        3: EthernetRegister(
            identifier='', units='', subnode=3, address=0x06DC,
            cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
        )
    }
    STORE_COCO_ALL = EthernetRegister(
        identifier='', units='', subnode=0, address=0x06DB, cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    )
    STORE_MOCO_ALL_REGISTERS = {
        1: EthernetRegister(
            identifier='', units='', subnode=1, address=0x06DB,
            cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
        ),
        2: EthernetRegister(
            identifier='', units='', subnode=2, address=0x06DB,
            cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
        ),
        3: EthernetRegister(
            identifier='', units='', subnode=3, address=0x06DB,
            cyclic='CONFIG', dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
        )
    }
    CONTROL_WORD_REGISTERS = {
        1: EthernetRegister(
            identifier='', units='', subnode=1, address=0x0010,
            cyclic='CYCLIC_RX', dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
        ),
        2: EthernetRegister(
            identifier='', units='', subnode=2, address=0x0010,
            cyclic='CYCLIC_RX', dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
        ),
        3: EthernetRegister(
            identifier='', units='', subnode=3, address=0x0010,
            cyclic='CYCLIC_RX', dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
        )
    }
    SERIAL_NUMBER_REGISTERS = {
        0: EthernetRegister(
            identifier='DRV_ID_SERIAL_NUMBER', units='', subnode=0,
            address=0x06E6, cyclic='CONFIG', dtype=REG_DTYPE.U32,
            access=REG_ACCESS.RO
        ),
        1: EthernetRegister(
            identifier='DRV_ID_SERIAL_NUMBER', units='', subnode=1,
            address=0x06E6, cyclic='CONFIG', dtype=REG_DTYPE.U32,
            access=REG_ACCESS.RO
        )
    }
    SOFTWARE_VERSION_REGISTERS = {
        0: EthernetRegister(
            identifier='DRV_ID_SOFTWARE_VERSION', units='', subnode=0,
            address=0x06E4, cyclic='CONFIG', dtype=REG_DTYPE.STR,
            access=REG_ACCESS.RO
        ),
        1: EthernetRegister(
            identifier='DRV_ID_SOFTWARE_VERSION', units='', subnode=1,
            address=0x06E4, cyclic='CONFIG', dtype=REG_DTYPE.STR,
            access=REG_ACCESS.RO
        )
    }
    PRODUCT_ID_REGISTERS = {
        0: EthernetRegister(
            identifier='DRV_ID_PRODUCT_CODE', units='', subnode=0,
            address=0x06E1, cyclic='CONFIG', dtype=REG_DTYPE.U32,
            access=REG_ACCESS.RO
        ),
        1: EthernetRegister(
            identifier='DRV_ID_PRODUCT_CODE', units='', subnode=1,
            address=0x06E1, cyclic='CONFIG', dtype=REG_DTYPE.U32,
            access=REG_ACCESS.RO
        )
    }
    REVISION_NUMBER_REGISTERS = {
        0: EthernetRegister(
            identifier='DRV_ID_REVISION_NUMBER', units='', subnode=0,
            address=0x06E2, cyclic='CONFIG', dtype=REG_DTYPE.U32,
            access=REG_ACCESS.RO
        ),
        1: EthernetRegister(
            identifier='DRV_ID_REVISION_NUMBER', units='', subnode=1,
            address=0x06E2, cyclic='CONFIG', dtype=REG_DTYPE.U32,
            access=REG_ACCESS.RO
        )
    }
    MONITORING_DIST_ENABLE = EthernetRegister(
        identifier='', units='', subnode=0, address=0x00C0, cyclic='CONFIG',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
    )
    MONITORING_REMOVE_DATA = EthernetRegister(
        identifier='', units='', subnode=0, address=0x00EA, cyclic='CONFIG',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.WO
    )
    MONITORING_NUMBER_MAPPED_REGISTERS = EthernetRegister(
        identifier='', units='', subnode=0, address=0x00E3, cyclic='CONFIG',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
    )
    MONITORING_BYTES_PER_BLOCK = EthernetRegister(
        identifier='', units='', subnode=0, address=0x00E4, cyclic='CONFIG',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
    )
    MONITORING_ACTUAL_NUMBER_BYTES = EthernetRegister(
        identifier='', units='', subnode=0, address=0x00B7, cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RO
    )
    MONITORING_DATA = EthernetRegister(
        identifier='', units='', subnode=0, address=0x00B2, cyclic='CONFIG',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.RO
    )
    DISTURBANCE_ENABLE = EthernetRegister(
        identifier='', units='', subnode=0, address=0x00C7, cyclic='CONFIG',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
    )
    DISTURBANCE_REMOVE_DATA = EthernetRegister(
        identifier='', units='', subnode=0, address=0x00EB, cyclic='CONFIG',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.WO
    )
    DISTURBANCE_NUMBER_MAPPED_REGISTERS = EthernetRegister(
        identifier='', units='', subnode=0, address=0x00E8, cyclic='CONFIG',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.RW
    )
    DIST_NUMBER_SAMPLES = EthernetRegister(
        identifier='', units='', subnode=0, address=0x00C4, cyclic='CONFIG',
        dtype=REG_DTYPE.U32, access=REG_ACCESS.RW
    )
    DIST_DATA = EthernetRegister(
        identifier='', units='', subnode=0, address=0x00B4, cyclic='CONFIG',
        dtype=REG_DTYPE.U16, access=REG_ACCESS.WO
    )

    def __init__(self, socket, dictionary_path=None,
                 servo_status_listener=False):
        self.socket = socket
        self.ip_address, self.port = self.socket.getpeername()
        if dictionary_path is not None:
            self._dictionary = EthernetDictionary(dictionary_path)
        else:
            self._dictionary = None
        super(EthernetServo, self).__init__(self.ip_address,
                                            servo_status_listener)

    def store_tcp_ip_parameters(self):
        """Stores the TCP/IP values. Affects IP address,
        subnet mask and gateway"""
        self.write(reg=self.STORE_COCO_ALL,
                   data=PASSWORD_STORE_RESTORE_TCP_IP,
                   subnode=0)
        logger.info('Store TCP/IP successfully done.')

    def restore_tcp_ip_parameters(self):
        """Restores the TCP/IP values back to default. Affects
        IP address, subnet mask and gateway"""
        self.write(reg=self.RESTORE_COCO_ALL,
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

        self.write(self.COMMS_ETH_IP, int_ip_address)
        self.write(self.COMMS_ETH_NET_MASK, int_subnet_mask)
        self.write(self.COMMS_ETH_NET_GATEWAY, int_gateway)

        try:
            self.store_tcp_ip_parameters()
        except ILError:
            self.store_parameters()

    def write(self, reg, data, subnode=1):
        """Writes data to a register.

        Args:
            reg (EthernetRegister, str): Target register to be written.
            data (int, str, float): Data to be written.
            subnode (int): Target axis of the drive.

        """
        _reg = self._get_reg(reg, subnode)
        if isinstance(data, float) and _reg.dtype != REG_DTYPE.FLOAT:
            data = int(data)
        data_bytes = convert_dtype_to_bytes(data, _reg.dtype)
        self._send_mcb_frame(MCB_CMD_WRITE, _reg.address,
                             _reg.subnode, data_bytes)

    def read(self, reg, subnode=1):
        """Read a register value from servo.

        Args:
            reg (str, Register): Register.
            subnode (int): Target axis of the drive.

        Returns:
            int, float or str: Value stored in the register.
        """
        _reg = self._get_reg(reg, subnode)
        data = self._send_mcb_frame(MCB_CMD_READ, _reg.address, _reg.subnode)
        return convert_bytes_to_dtype(data, _reg.dtype)

    def disturbance_write_data(self, channels, dtypes, data_arr):
        """Write disturbance data.

        Args:
            channels (int or list of int): Channel identifier.
            dtypes (int or list of int): Data type.
            data_arr (list or list of list): Data array.

        """
        data, chunks = self._disturbance_create_data_chunks(channels,
                                                            dtypes,
                                                            data_arr,
                                                            ETH_MAX_WRITE_SIZE)
        for chunk in chunks:
            self._send_mcb_frame(MCB_CMD_WRITE, self.DIST_DATA.address,
                                 self.DIST_DATA.subnode, chunk)
        self.disturbance_data = data
        self.disturbance_data_size = len(data)

    def replace_dictionary(self, dictionary):
        """Deletes and creates a new instance of the dictionary.

        Args:
            dictionary (str): Dictionary.

        """
        self._dictionary = EthernetDictionary(dictionary)

    def _send_mcb_frame(self, cmd, reg, subnode, data=None):
        """Send an MCB frame to the drive.

        Args:
            cmd (int): Read/write command.
            reg (int): Register address to be read/written.
            subnode (int): Target axis of the drive.
            data (bytes): Data to be written to the register.

        Returns:
            bytes: The response frame.
        """
        frame = MCB.build_mcb_frame(cmd, subnode, reg, data)
        self._lock.acquire()
        try:
            try:
                self.socket.sendall(frame)
            except socket.error as e:
                raise ILIOError('Error sending data.') from e
            try:
                response = self.socket.recv(ETH_BUF_SIZE)
            except socket.timeout as e:
                raise ILTimeoutError('Timeout while receiving data.') from e
            except socket.error as e:
                raise ILIOError('Error receiving data.') from e
        except (ILIOError, ILTimeoutError) as e:
            raise e
        finally:
            self._lock.release()
        return MCB.read_mcb_data(reg, response)

    def _monitoring_read_data(self):
        """Read monitoring data frame."""
        return self._send_mcb_frame(MCB_CMD_READ,
                                    self.MONITORING_DATA.address,
                                    self.MONITORING_DATA.subnode)
