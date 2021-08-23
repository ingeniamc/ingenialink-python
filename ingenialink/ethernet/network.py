from ..network import NET_PROT, NET_TRANS_PROT
from .servo import EthernetServo
from ingenialink.ipb.network import IPBNetwork
from ingenialink.utils._utils import *
from .._ingenialink import lib, ffi
from ingenialink.utils.udp import UDP
import ingenialogger

from ftplib import FTP
from os import path
from time import sleep

FTP_SESSION_OK_CODE = "220"
FTP_LOGIN_OK_CODE = "230"
FTP_FILE_TRANSFER_OK_CODE = "226"
FTP_CLOSE_OK_CODE = "221"

CMD_CHANGE_CPU = 0x67E4

logger = ingenialogger.get_logger(__name__)


class EthernetNetwork(IPBNetwork):
    """Network for all Ethernet communications."""
    def __init__(self):
        super(EthernetNetwork, self).__init__()

    @staticmethod
    def load_firmware(fw_file, target="192.168.2.22", ftp_user="", ftp_pwd=""):
        """Loads a given firmware file to the target slave.

        Args:
            fw_file (str): Path to the firmware file to be loaded.
            target (str): IP of the target slave.
            ftp_user (str): FTP user to connect with.
            ftp_pwd (str): FTP password for the given user.

        Raises:
            ILError: If the loading firmware process fails.

        """
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
                "STOR {}".format(path.basename(file.name)), file)
            logger.info(ftp_output)
            if FTP_FILE_TRANSFER_OK_CODE not in ftp_output:
                raise_err("Unable to load the FW file through FTP")

            # Close FTP session.
            logger.info("Closing FTP session...")
            ftp.close()

            # Close the temporal file
            file.close()

        except Exception as e:
            raise_err("Exception when flashing drive: {}".format(e))

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

        """
        r = 0
        upd = UDP(port, ip)

        if moco_file and path.isfile(moco_file):
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
                        data = data + bytes([int(words[data_start_byte], 16)])
                        data_start_byte = data_start_byte + 1

                    # Send message
                    upd.raw_cmd(node, subnode, cmd, data)

                    if cmd == CMD_CHANGE_CPU:
                        sleep(1)

                logger.info("Bootload process succeeded")
            except Exception as e:
                logger.error('Error during bootload process. %s', e)
                r = -2
        else:
            logger.error('File not found')
            r = -1

        return r

    def scan_slaves(self):
        raise NotImplementedError

    def connect_to_slave(self, target, dictionary=None, port=1061,
                         communication_protocol=NET_TRANS_PROT.UDP):
        """Connects to a slave through the given network settings.

        Args:
            target (str): IP of the target slave.
            dictionary (str): Path to the target dictionary file.
            port (int): Port to connect to the slave.
            communication_protocol (NET_TRANS_PROT): Communication protocol, UPD or TCP.

        Returns:
            EthernetServo: Instance of the servo connected.

        """
        net__ = ffi.new('il_net_t **')
        servo__ = ffi.new('il_servo_t **')
        _dictionary = cstr(dictionary) if dictionary else ffi.NULL
        _target = cstr(target) if target else ffi.NULL

        r = lib.il_servo_lucky_eth(NET_PROT.ETH.value, net__, servo__,
                                   _dictionary, _target,
                                   port, communication_protocol.value)

        raise_err(r)

        net_ = ffi.cast('il_net_t *', net__[0])
        servo_ = ffi.cast('il_servo_t *', servo__[0])

        self._from_existing(net_)
        servo = EthernetServo._from_existing(servo_, _dictionary)
        servo._cffi_network = self._cffi_network
        servo.target = target
        servo._dictionary = dictionary
        servo.port = port
        servo.communication_protocol = communication_protocol

        self.servos.append(servo)

        return servo

    def disconnect_from_slave(self, servo):
        """Disconnects the slave from the network.

        Args:
            servo (EthernetServo): Instance of the servo connected.

        """
        # TODO: This stops all connections no only the target servo.
        self.servos.remove(servo)
        if len(self.servos) == 0:
            self.stop_network_monitor()
            self.close_socket()
            self.destroy_network()
        self._cffi_network = None

    @property
    def protocol(self):
        """NET_PROT: Obtain network protocol."""
        return NET_PROT.ETH
