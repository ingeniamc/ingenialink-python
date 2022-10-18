import ftplib

from .servo import EthernetServo
from ingenialink.utils.udp import UDP
from ingenialink.utils._utils import *
from ..network import NET_PROT
from ingenialink.network import Network, NET_STATE, NET_DEV_EVT
from ingenialink.exceptions import ILFirmwareLoadError

from ftplib import FTP
from time import sleep

import os
import socket
import ingenialogger
from threading import Thread

from ping3 import ping

logger = ingenialogger.get_logger(__name__)

FTP_SESSION_OK_CODE = "220"
FTP_LOGIN_OK_CODE = "230"
FTP_FILE_TRANSFER_OK_CODE = "226"
FTP_CLOSE_OK_CODE = "221"

CMD_CHANGE_CPU = 0x67E4

MAX_NUM_UNSUCCESSFUL_PINGS = 3


class NetStatusListener(Thread):
    """Network status listener thread to check if the drive is alive.

    Args:
        network (EthernetNetwork): Network instance of the Ethernet communication.

    """

    def __init__(self, network):
        super(NetStatusListener, self).__init__()
        self.__network = network
        self.__state = NET_STATE.CONNECTED
        self.__stop = False
        self.__max_unsuccessful_pings = MAX_NUM_UNSUCCESSFUL_PINGS

    def run(self):
        servo = self.__network.servos[0]
        unsuccessful_pings = 0
        while not self.__stop:
            response = ping(servo.ip_address, timeout=1)
            if not isinstance(response, float):
                unsuccessful_pings += 1
            else:
                unsuccessful_pings -= 1
                unsuccessful_pings = max(0, unsuccessful_pings)
            if unsuccessful_pings > self.__max_unsuccessful_pings:
                if self.__state != NET_STATE.DISCONNECTED:
                    self.__state = NET_STATE.DISCONNECTED
                    self.__network.status = NET_STATE.DISCONNECTED
                    self.__network._notify_status(NET_DEV_EVT.REMOVED)
                unsuccessful_pings = self.__max_unsuccessful_pings
            elif unsuccessful_pings == 0:
                if self.__state != NET_STATE.CONNECTED:
                    self.__network.status = NET_STATE.CONNECTED
                    self.__state = NET_STATE.CONNECTED
                    self.__network._notify_status(NET_DEV_EVT.ADDED)
            sleep(1)

    def stop(self):
        self.__stop = True


class EthernetNetwork(Network):
    """Network for all Ethernet communications."""
    def __init__(self):
        super(EthernetNetwork, self).__init__()
        self.__net_state = NET_STATE.DISCONNECTED
        self.socket = None
        self.__listener_net_status = None
        self.__observers_net_state = []

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
                         servo_status_listener=False,
                         net_status_listener=False):
        """Connects to a slave through the given network settings.

        Args:
            target (str): IP of the target slave.
            dictionary (str): Path to the target dictionary file.
            port (int): Port to connect to the slave.
            servo_status_listener (bool): Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener (bool): Toggle the listener of the network
                status, connection and disconnection.

        Returns:
            EthernetServo: Instance of the servo connected.

        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.connect((target, port))
        servo = EthernetServo(self.socket, dictionary,
                              servo_status_listener)

        self.servos.append(servo)

        if net_status_listener:
            self.start_status_listener()
        else:
            self.stop_status_listener()

        return servo

    def disconnect_from_slave(self, servo):
        """Disconnects the slave from the network.

        Args:
            servo (EthernetServo): Instance of the servo connected.

        """
        # TODO: This stops all connections no only the target servo.
        self.servos.remove(servo)
        servo.stop_status_listener()
        if len(self.servos) == 0:
            self.stop_status_listener()
            self.close_socket()

    def close_socket(self):
        """Closes the established network socket."""
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()

    def start_status_listener(self):
        """Start monitoring network events (CONNECTION/DISCONNECTION)."""
        listener = NetStatusListener(self)
        listener.start()
        self.__listener_net_status = listener

    def stop_status_listener(self):
        """Stops the NetStatusListener from listening to the drive."""
        if self.__listener_net_status is not None and \
                self.__listener_net_status.is_alive():
            self.__listener_net_status.stop()
            self.__listener_net_status.join()
        self.__listener_net_status = None

    def _notify_status(self, status):
        """Notify subscribers of a network state change."""
        for callback in self.__observers_net_state:
            callback(status)

    def subscribe_to_status(self, callback):
        """Subscribe to network state changes.

        Args:
            callback (function): Callback function.

        """
        if callback in self.__observers_net_state:
            logger.info('Callback already subscribed.')
            return
        self.__observers_net_state.append(callback)

    def unsubscribe_from_status(self, callback):
        """Unsubscribe from network state changes.

        Args:
            callback (function): Callback function.

        """
        if callback not in self.__observers_net_state:
            logger.info('Callback not subscribed.')
            return
        self.__observers_net_state.remove(callback)

    @property
    def protocol(self):
        """NET_PROT: Obtain network protocol."""
        return NET_PROT.ETH

    @property
    def status(self):
        """NET_STATE: Network state."""
        return self.__net_state

    @status.setter
    def status(self, new_state):
        self.__net_state = new_state
