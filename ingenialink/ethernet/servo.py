from .._ingenialink import lib, ffi
from ingenialink.network import NET_TRANS_PROT
from ingenialink.constants import PASSWORD_STORE_RESTORE_TCP_IP
from ingenialink.ipb.register import IPBRegister, REG_DTYPE, REG_ACCESS
from ingenialink.ipb.servo import IPBServo, STORE_COCO_ALL, RESTORE_COCO_ALL

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


class EthernetServo(IPBServo):
    """Servo object for all the Ethernet slave functionalities.

    Args:
        cffi_servo (CData): CData instance of the servo.
        cffi_net (CData): CData instance of the network.
        target (str): Target ID for the slave.
        port (int): Port for the communication.
        communication_protocol (NET_TRANS_PROT): Transmission protocol.
        dictionary_path (str): Path to the dictionary.
        servo_status_listener (bool): Toggle the listener of the servo for
        its status, errors, faults, etc.

    """
    def __init__(self, cffi_servo, cffi_net, target, port, communication_protocol,
                 dictionary_path=None, servo_status_listener=True):
        servo = ffi.gc(cffi_servo, lib.il_servo_fake_destroy)
        super(EthernetServo, self).__init__(
            servo, cffi_net, target, dictionary_path)
        self.port = port
        """int: Port number used for connections to the servo."""
        self.communication_protocol = communication_protocol
        """NET_TRANS_PROT: Protocol used to connect to the servo."""

        if not servo_status_listener:
            self.stop_servo_monitoring()
        else:
            self.start_servo_monitoring()

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

        """
        int_ip_address = self._convert_ip_to_int(ip_address)
        int_subnet_mask = self._convert_ip_to_int(subnet_mask)
        int_gateway = self._convert_ip_to_int(gateway)

        self.write(COMMS_ETH_IP, int_ip_address)
        self.write(COMMS_ETH_NET_MASK, int_subnet_mask)
        self.write(COMMS_ETH_NET_GATEWAY, int_gateway)

        self.store_tcp_ip_parameters()

    @staticmethod
    def _convert_ip_to_int(ip):
        """Converts a string type IP to its integer value.

        Args:
            ip (str): IP to be converted.

        """
        split_ip = ip.split('.')
        drive_ip1 = int(split_ip[0]) << 24
        drive_ip2 = int(split_ip[1]) << 16
        drive_ip3 = int(split_ip[2]) << 8
        drive_ip4 = int(split_ip[3])
        return drive_ip1 + drive_ip2 + drive_ip3 + drive_ip4

    @staticmethod
    def _convert_int_to_ip(int_ip):
        """Converts an integer type IP to its string form.

        Args:
            int_ip (int): IP to be converted.

        """
        drive_ip1 = (int_ip >> 24) & 0x000000FF
        drive_ip2 = (int_ip >> 16) & 0x000000FF
        drive_ip3 = (int_ip >> 8) & 0x000000FF
        drive_ip4 = int_ip & 0x000000FF
        return '{}.{}.{}.{}'.format(drive_ip1, drive_ip2, drive_ip3, drive_ip4)
