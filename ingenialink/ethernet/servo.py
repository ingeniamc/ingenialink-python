from .._ingenialink import lib, ffi
from ingenialink.ipb.servo import IPBServo, STORE_COCO_ALL, RESTORE_COCO_ALL
from ingenialink.network import NET_TRANS_PROT
from ingenialink.constants import PASSWORD_STORE_RESTORE_TCP_IP, \
    PASSWORD_STORE_RESTORE_SUB_0

import ingenialogger
logger = ingenialogger.get_logger(__name__)


class EthernetServo(IPBServo):
    """Servo object for all the Ethernet slave functionalities.

    Args:
        cffi_servo (CData): CData instance of the servo.
        cffi_net (CData): CData instance of the network.
        target (str): Target ID for the slave.
        port (int): Port for the communication.
        communication_protocol (NET_TRANS_PROT): Transmission protocol.
        dictionary_path (str): Path to the dictionary.

    """
    def __init__(self, cffi_servo, cffi_net, target, port, communication_protocol,
                 dictionary_path=None):
        servo = ffi.gc(cffi_servo, lib.il_servo_fake_destroy)
        super(EthernetServo, self).__init__(
            servo, cffi_net, target, dictionary_path)
        self.port = port
        """int: Port number used for connections to the servo."""
        self.communication_protocol = communication_protocol
        """NET_TRANS_PROT: Protocol used to connect to the servo."""

    def store_tcp_ip_parameters(self):
        """Stores the TCP/IP values. Affects IP address,
        network mask and gateway"""
        self.write(reg=STORE_COCO_ALL,
                   data=PASSWORD_STORE_RESTORE_TCP_IP,
                   subnode=0)
        logger.info('Store TCP/IP successfully done.')

    def restore_tcp_ip_parameters(self):
        """Restores the TCP/IP values back to default. Affects
        IP address, network mask and gateway"""
        self.write(reg=RESTORE_COCO_ALL,
                   data=PASSWORD_STORE_RESTORE_TCP_IP,
                   subnode=0)
        logger.info('Restore TCP/IP successfully done.')
