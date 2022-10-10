import ftplib

from .servo import EthernetServo
from ingenialink.constants import *
from .._ingenialink import lib, ffi
from ingenialink.utils.udp import UDP
from ingenialink.utils._utils import *
from ..network import NET_PROT, NET_TRANS_PROT
from ingenialink.ipb.network import IPBNetwork
from ingenialink.exceptions import ILFirmwareLoadError

from ftplib import FTP
from time import sleep

import os
import socket
import ingenialogger
logger = ingenialogger.get_logger(__name__)

FTP_SESSION_OK_CODE = "220"
FTP_LOGIN_OK_CODE = "230"
FTP_FILE_TRANSFER_OK_CODE = "226"
FTP_CLOSE_OK_CODE = "221"

CMD_CHANGE_CPU = 0x67E4


class EthernetNetwork(IPBNetwork):
    """Network for all Ethernet communications."""
    def __init__(self):
        super(EthernetNetwork, self).__init__()
        self.socket = None

    @staticmethod
    def load_firmware(fw_file, target="192.168.2.22", ftp_user="", ftp_pwd=""):
        """Loads a given firmware file to the target slave.

        .. warning ::
            It is needed to disconnect the drive(:func:`disconnect_from_slave`)
            after loading the firmware since the `Servo` object's data will
            become obsolete.

        Args:
            fw_file (str): Path to the firmware file to be loaded.
            target (str): IP of the target slave.
            ftp_user (str): FTP user to connect with.
            ftp_pwd (str): FTP password for the given user.

        Raises:
            ILError: If the loading firmware process fails.

        """
        if not os.path.isfile(fw_file):
            raise FileNotFoundError('Could not find {}.'.format(fw_file))

        try:
            file = open(fw_file, 'rb')
            ftp_output = None
            ftp = FTP()

            # Start a FTP session. Drive must be in BOOT mode.
            logger.info("Starting FTP session...")
            ftp_output = ftp.connect(target)
            logger.info(ftp_output)
            if FTP_SESSION_OK_CODE not in ftp_output:
                raise_err("Unable to open FTP session")

            # Login into FTP session.
            logger.info("Logging into FTP session...")
            ftp_output = ftp.login(ftp_user, ftp_pwd)
            logger.info(ftp_output)
            if FTP_LOGIN_OK_CODE not in ftp_output:
                raise_err("Unable to login the FTP session")

            # Load file through FTP.
            logger.info("Uploading firmware file...")
            ftp.set_pasv(False)
            ftp_output = ftp.storbinary(
                "STOR {}".format(os.path.basename(file.name)), file)
            logger.info(ftp_output)
            if FTP_FILE_TRANSFER_OK_CODE not in ftp_output:
                raise_err("Unable to load the FW file through FTP")

            # Close FTP session.
            logger.info("Closing FTP session...")
            ftp.close()

            # Close the temporal file
            file.close()

        except Exception as e:
            logger.error(e)
            raise ILFirmwareLoadError('Error during bootloader process.')

    @staticmethod
    def load_firmware_moco(node, subnode, ip, port, moco_file):
        """Update MOCO firmware through UDP protocol.

        Args:
            node: Network node.
            subnode: Drive subnode.
            ip: Drive address IP.
            port: Drive port.
            moco_file: Path to the firmware file.

        Returns:
            int: Result code.

        Raises:
            ILFirmwareLoadError: The firmware load process fails
                with an error message.
        """
        r = 0
        upd = UDP(port, ip)

        if not moco_file or not os.path.isfile(moco_file):
            raise ILFirmwareLoadError('File not found')
        moco_in = open(moco_file, "r")

        logger.info("Loading firmware...")
        try:
            for line in moco_in:
                words = line.split()

                # Get command and address
                cmd = int(words[1] + words[0], 16)
                data = b''
                data_start_byte = 2
                while data_start_byte in range(data_start_byte, len(words)):
                    # Load UDP data
                    data += bytes([int(words[data_start_byte], 16)])
                    data_start_byte += 1

                # Send message
                upd.raw_cmd(node, subnode, cmd, data)

                if cmd == CMD_CHANGE_CPU:
                    sleep(1)

            logger.info("Bootload process succeeded")
        except ftplib.error_temp as e:
            logger.error(e)
            raise ILFirmwareLoadError('Firewall might be blocking the access.')
        except Exception as e:
            logger.error(e)
            raise ILFirmwareLoadError('Error during bootloader process.')

    def scan_slaves(self):
        raise NotImplementedError

    def connect_to_slave(self, target, dictionary=None, port=1061,
                         communication_protocol=NET_TRANS_PROT.UDP,
                         reconnection_retries=DEFAULT_MESSAGE_RETRIES,
                         reconnection_timeout=DEFAULT_MESSAGE_TIMEOUT,
                         servo_status_listener=False,
                         net_status_listener=False):
        """Connects to a slave through the given network settings.

        Args:
            target (str): IP of the target slave.
            dictionary (str): Path to the target dictionary file.
            port (int): Port to connect to the slave.
            communication_protocol (NET_TRANS_PROT): Communication protocol, UPD or TCP.
            reconnection_retries (int): Number of reconnection retried before declaring
                a connected or disconnected stated.
            reconnection_timeout (int): Time in ms of the reconnection timeout.
            servo_status_listener (bool): Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener (bool): Toggle the listener of the network
                status, connection and disconnection.

        Returns:
            EthernetServo: Instance of the servo connected.

        """
        if communication_protocol == NET_TRANS_PROT.UDP:
            protocol = socket.SOCK_DGRAM
        else:
            protocol = socket.SOCK_STREAM
        self.socket = socket.socket(socket.AF_INET, protocol)
        self.socket.connect((target, port))
        servo = EthernetServo(self.socket, dictionary,
                              servo_status_listener)

        self.servos.append(servo)

        if net_status_listener:
            self.start_status_listener()
        else:
            self.stop_status_listener()

        self.set_reconnection_retries(reconnection_retries)
        self.set_recv_timeout(reconnection_timeout)

        return servo

    def disconnect_from_slave(self, servo):
        """Disconnects the slave from the network.

        Args:
            servo (EthernetServo): Instance of the servo connected.

        """
        # TODO: This stops all connections no only the target servo.
        self.servos.remove(servo)
        if len(self.servos) == 0:
            self.stop_status_listener()
            lib.il_net_mon_stop(self._cffi_network)
            self.close_socket()
        self._cffi_network = None

    def close_socket(self):
        """Closes the established network socket."""
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()

    @property
    def protocol(self):
        """NET_PROT: Obtain network protocol."""
        return NET_PROT.ETH
