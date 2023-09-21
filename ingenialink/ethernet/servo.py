import ipaddress
import socket

from ingenialink.exceptions import ILError, ILTimeoutError, ILIOError, ILWrongRegisterError
from ingenialink.constants import PASSWORD_STORE_RESTORE_TCP_IP
from ingenialink.ethernet.register import EthernetRegister
from ingenialink.constants import MCB_CMD_READ, MCB_CMD_WRITE, ETH_MAX_WRITE_SIZE, ETH_BUF_SIZE
from ingenialink.enums.register import REG_DTYPE, REG_ACCESS
from ingenialink.servo import Servo
from ingenialink.utils.mcb import MCB
from ingenialink.utils._utils import (
    convert_bytes_to_dtype,
    convert_dtype_to_bytes,
    convert_ip_to_int,
)
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

    DICTIONARY_CLASS = EthernetDictionary
    MAX_WRITE_SIZE = ETH_MAX_WRITE_SIZE

    COMMS_ETH_IP = "COMMS_ETH_IP"
    COMMS_ETH_NET_MASK = "COMMS_ETH_NET_MASK"
    COMMS_ETH_NET_GATEWAY = "COMMS_ETH_GW"
    MONITORING_DATA = EthernetRegister(
        identifier="",
        units="",
        subnode=0,
        address=0x00B2,
        cyclic="CONFIG",
        dtype=REG_DTYPE.U16,
        access=REG_ACCESS.RO,
    )
    DIST_DATA = EthernetRegister(
        identifier="",
        units="",
        subnode=0,
        address=0x00B4,
        cyclic="CONFIG",
        dtype=REG_DTYPE.U16,
        access=REG_ACCESS.WO,
    )

    def __init__(self, socket, dictionary_path=None, servo_status_listener=False):
        self.socket = socket
        self.ip_address, self.port = self.socket.getpeername()
        super(EthernetServo, self).__init__(self.ip_address, dictionary_path, servo_status_listener)

    def store_tcp_ip_parameters(self):
        """Stores the TCP/IP values. Affects IP address,
        subnet mask and gateway"""
        self.write(reg=self.STORE_COCO_ALL, data=PASSWORD_STORE_RESTORE_TCP_IP, subnode=0)
        logger.info("Store TCP/IP successfully done.")

    def restore_tcp_ip_parameters(self):
        """Restores the TCP/IP values back to default. Affects
        IP address, subnet mask and gateway"""
        self.write(reg=self.RESTORE_COCO_ALL, data=PASSWORD_STORE_RESTORE_TCP_IP, subnode=0)
        logger.info("Restore TCP/IP successfully done.")

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
        net = ipaddress.IPv4Network(f"{drive_ip}/{subnet_mask}", strict=False)

        if gateway_ip not in net:
            raise ValueError(
                f"Drive IP {ip_address} and Gateway IP {gateway} are not on the same network."
            )

        int_ip_address = convert_ip_to_int(ip_address)
        int_subnet_mask = convert_ip_to_int(subnet_mask)
        int_gateway = convert_ip_to_int(gateway)

        self.write(self.COMMS_ETH_IP, int_ip_address, subnode=0)
        self.write(self.COMMS_ETH_NET_MASK, int_subnet_mask, subnode=0)
        self.write(self.COMMS_ETH_NET_GATEWAY, int_gateway, subnode=0)

        try:
            self.store_tcp_ip_parameters()
        except ILError:
            self.store_parameters()

    def _write_raw(self, reg, data):
        self._send_mcb_frame(MCB_CMD_WRITE, reg.address, reg.subnode, data)

    def _read_raw(self, reg):
        return self._send_mcb_frame(MCB_CMD_READ, reg.address, reg.subnode)

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
                raise ILIOError("Error sending data.") from e
            try:
                return self.__receive_mcb_frame(reg)
            except ILWrongRegisterError as e:
                logger.error(e)
                return self.__receive_mcb_frame(reg)
        finally:
            self._lock.release()

    def __receive_mcb_frame(self, reg: int) -> bytes:
        """Receive frame from socket and return MCB data

        Args:
            reg: expected address

        Returns:
            MCB message data in bytes

        Raises:
            ILTimeoutError: socket timeout
            ILIOError: socket error

        """
        try:
            response = self.socket.recv(ETH_BUF_SIZE)
        except socket.timeout as e:
            raise ILTimeoutError("Timeout while receiving data.") from e
        except socket.error as e:
            raise ILIOError("Error receiving data.") from e
        return MCB.read_mcb_data(reg, response)
