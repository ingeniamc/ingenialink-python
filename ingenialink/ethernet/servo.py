import ipaddress
import socket
from typing import Callable, Optional

import ingenialogger

from ingenialink.constants import (
    ETH_BUF_SIZE,
    ETH_MAX_WRITE_SIZE,
    MCB_CMD_READ,
    MCB_CMD_WRITE,
    PASSWORD_STORE_RESTORE_TCP_IP,
)
from ingenialink.dictionary import Interface
from ingenialink.ethernet.register import EthernetRegister
from ingenialink.exceptions import ILError, ILIOError, ILTimeoutError, ILWrongRegisterError
from ingenialink.servo import Servo
from ingenialink.utils._utils import convert_ip_to_int
from ingenialink.utils.mcb import MCB

logger = ingenialogger.get_logger(__name__)


class EthernetServo(Servo):
    """Servo object for all the Ethernet slave functionalities.

    Args:
        socket: Socket.
        dictionary_path: Path to the dictionary.
        servo_status_listener: Toggle the listener of the servo for
            its status, errors, faults, etc.
        is_eoe: True if communication is EoE. ``False`` by default.

    """

    MAX_WRITE_SIZE = ETH_MAX_WRITE_SIZE

    COMMS_ETH_IP = "COMMS_ETH_IP"
    COMMS_ETH_NET_MASK = "COMMS_ETH_NET_MASK"
    COMMS_ETH_NET_GATEWAY = "COMMS_ETH_GW"
    COMMS_ETH_MAC = "COMMS_ETH_MAC"

    interface = Interface.ETH

    def __init__(
        self,
        socket: socket.socket,
        dictionary_path: str,
        servo_status_listener: bool = False,
        is_eoe: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ) -> None:
        if is_eoe:
            self.interface = Interface.EoE
        self.socket = socket
        self.ip_address, self.port = self.socket.getpeername()
        super().__init__(
            self.ip_address,
            dictionary_path,
            servo_status_listener,
            disconnect_callback=disconnect_callback,
        )

    def store_tcp_ip_parameters(self) -> None:
        """Stores the TCP/IP values.

        Affects IP address, subnet mask, gateway and mac_address.
        """
        self.write(reg=self.STORE_COCO_ALL, data=PASSWORD_STORE_RESTORE_TCP_IP, subnode=0)
        logger.info("Store TCP/IP successfully done.")

    def restore_tcp_ip_parameters(self) -> None:
        """Restores the TCP/IP values back to default.

        Affects IP address, subnet mask and gateway.
        """
        self.write(reg=self.RESTORE_COCO_ALL, data=PASSWORD_STORE_RESTORE_TCP_IP, subnode=0)
        logger.info("Restore TCP/IP successfully done.")

    def change_tcp_ip_parameters(
        self, ip_address: str, subnet_mask: str, gateway: str, mac_address: Optional[int] = None
    ) -> None:
        """Stores the TCP/IP values.

        Affects IP address, network mask ,gateway and mac_address.

        .. note::
            The drive needs a power cycle after this
            in order for the changes to be properly applied.

        Args:
            ip_address: IP Address to be changed.
            subnet_mask: Subnet mask to be changed.
            gateway: Gateway to be changed.
            mac_address: The MAC address to be set.

        Raises:
            ValueError: If the drive or gateway IP is not a
                valid IP address.
            ValueError: If the drive IP and gateway IP are not
                on the same network.
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

        if mac_address is not None:
            self.set_mac_address(mac_address)

        try:
            self.store_tcp_ip_parameters()
        except ILError:
            self.store_parameters()

    def get_mac_address(self) -> int:
        """Get the MAC address of the servo.

        Raises:
            ValueError: if there is an error retrieving the MAC address.

        Returns:
            The servo's MAC address.
        """
        mac_address = self.read(self.COMMS_ETH_MAC, subnode=0)
        if not isinstance(mac_address, int):
            raise ValueError(
                f"Error retrieving the MAC address. Expected an int, got: {type(mac_address)}"
            )
        return mac_address

    def set_mac_address(self, mac_address: int) -> None:
        """Set the MAC address of the servo.

        Args:
            mac_address: The MAC address to be set.

        """
        self.write(self.COMMS_ETH_MAC, subnode=0, data=mac_address)

    def _write_raw(self, reg: EthernetRegister, data: bytes) -> None:  # type: ignore [override]
        self._send_mcb_frame(MCB_CMD_WRITE, reg.address, reg.subnode, data)

    def _read_raw(self, reg: EthernetRegister) -> bytes:  # type: ignore [override]
        return self._send_mcb_frame(MCB_CMD_READ, reg.address, reg.subnode)

    def _send_mcb_frame(
        self, cmd: int, reg: int, subnode: int, data: Optional[bytes] = None
    ) -> bytes:
        """Send an MCB frame to the drive.

        Args:
            cmd: Read/write command.
            reg: Register address to be read/written.
            subnode: Target axis of the drive.
            data: Data to be written to the register.

        Raises:
            ILIOError: If there is an error sending the data.

        Returns:
            The response frame.
        """
        frame = MCB.build_mcb_frame(cmd, subnode, reg, data)
        self._lock.acquire()
        try:
            try:
                self.socket.sendall(frame)
            except OSError as e:
                raise ILIOError("Error sending data.") from e
            try:
                return self.__receive_mcb_frame(reg)
            except ILWrongRegisterError as e:
                logger.error(e)
                return self.__receive_mcb_frame(reg)
            except ILTimeoutError as e:
                logger.error(f"{e}. Retrying..")
                self.socket.sendall(frame)
                return self.__receive_mcb_frame(reg)
        finally:
            self._lock.release()

    def __receive_mcb_frame(self, reg: int) -> bytes:
        """Receive frame from socket and return MCB data.

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
        except OSError as e:
            raise ILIOError("Error receiving data.") from e
        return MCB.read_mcb_data(reg, response)
