import ftplib
import time
from collections import defaultdict

from .servo import EthernetServo
from ingenialink.utils.udp import UDP
from ..network import NET_PROT
from ingenialink.network import Network, NET_STATE, NET_DEV_EVT
from ingenialink.exceptions import ILFirmwareLoadError, ILError, ILIOError
from ingenialink.constants import DEFAULT_ETH_CONNECTION_TIMEOUT

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
        self.__stop = False
        self.__max_unsuccessful_pings = MAX_NUM_UNSUCCESSFUL_PINGS

    def run(self):
        while not self.__stop:
            for servo in self.__network.servos:
                unsuccessful_pings = 0
                servo_ip = servo.ip_address
                servo_state = self.__network._get_servo_state(servo_ip)
                while unsuccessful_pings < self.__max_unsuccessful_pings:
                    response = ping(servo_ip, timeout=1)
                    if not isinstance(response, float):
                        unsuccessful_pings += 1
                    else:
                        break
                ping_response = unsuccessful_pings != self.__max_unsuccessful_pings
                if servo_state == NET_STATE.CONNECTED and not ping_response:
                    self.__network._notify_status(servo_ip, NET_DEV_EVT.REMOVED)
                    self.__network._set_servo_state(servo_ip, NET_STATE.DISCONNECTED)
                if servo_state == NET_STATE.DISCONNECTED and ping_response:
                    self.__network._notify_status(servo_ip, NET_DEV_EVT.ADDED)
                    self.__network._set_servo_state(servo_ip, NET_STATE.CONNECTED)
            time.sleep(0.25)

    def stop(self):
        self.__stop = True


class EthernetNetwork(Network):
    """Network for all Ethernet communications."""

    def __init__(self):
        super(EthernetNetwork, self).__init__()
        self.__servos_state = {}
        self.__listener_net_status = None
        self.__observers_net_state = defaultdict(list)

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
            raise FileNotFoundError(f"Could not find {fw_file}.")

        try:
            file = open(fw_file, "rb")
            ftp_output = None
            ftp = FTP()

            # Start a FTP session. Drive must be in BOOT mode.
            logger.info("Starting FTP session...")
            ftp_output = ftp.connect(target)
            logger.info(ftp_output)
            if FTP_SESSION_OK_CODE not in ftp_output:
                raise ILError("Unable to open FTP session")

            # Login into FTP session.
            logger.info("Logging into FTP session...")
            ftp_output = ftp.login(ftp_user, ftp_pwd)
            logger.info(ftp_output)
            if FTP_LOGIN_OK_CODE not in ftp_output:
                raise ILError("Unable to login the FTP session")

            # Load file through FTP.
            logger.info("Uploading firmware file...")
            ftp.set_pasv(False)
            ftp_output = ftp.storbinary(f"STOR {os.path.basename(file.name)}", file)
            logger.info(ftp_output)
            if FTP_FILE_TRANSFER_OK_CODE not in ftp_output:
                raise ILError("Unable to load the FW file through FTP")

            # Close FTP session.
            logger.info("Closing FTP session...")
            ftp.close()

            # Close the temporal file
            file.close()

        except Exception as e:
            logger.error(e)
            raise ILFirmwareLoadError("Error during bootloader process.")

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
            raise ILFirmwareLoadError("File not found")
        moco_in = open(moco_file, "r")

        logger.info("Loading firmware...")
        try:
            for line in moco_in:
                words = line.split()

                # Get command and address
                cmd = int(words[1] + words[0], 16)
                data = b""
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
            raise ILFirmwareLoadError("Firewall might be blocking the access.")
        except Exception as e:
            logger.error(e)
            raise ILFirmwareLoadError("Error during bootloader process.")

    def scan_slaves(self):
        raise NotImplementedError

    def connect_to_slave(
        self,
        target,
        dictionary=None,
        port=1061,
        connection_timeout=DEFAULT_ETH_CONNECTION_TIMEOUT,
        servo_status_listener=False,
        net_status_listener=False,
    ):
        """Connects to a slave through the given network settings.

        Args:
            target (str): IP of the target slave.
            dictionary (str): Path to the target dictionary file.
            port (int): Port to connect to the slave.
            connection_timeout (float): Time in seconds of the connection timeout.
            servo_status_listener (bool): Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener (bool): Toggle the listener of the network
                status, connection and disconnection.

        Returns:
            EthernetServo: Instance of the servo connected.

        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(connection_timeout)
        sock.connect((target, port))
        servo = EthernetServo(sock, dictionary, servo_status_listener)
        try:
            servo.get_state()
        except ILError as e:
            servo.stop_status_listener()
            raise ILError(f"Drive not found in IP {target}.") from e
        self.servos.append(servo)
        self._set_servo_state(target, NET_STATE.CONNECTED)

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
        self.servos.remove(servo)
        servo.stop_status_listener()
        self.close_socket(servo.socket)
        self._set_servo_state(servo.ip_address, NET_STATE.DISCONNECTED)
        if len(self.servos) == 0:
            self.stop_status_listener()

    @staticmethod
    def close_socket(sock):
        """Closes the established network socket."""
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()

    def start_status_listener(self):
        """Start monitoring network events (CONNECTION/DISCONNECTION)."""
        if self.__listener_net_status is None:
            listener = NetStatusListener(self)
            listener.start()
            self.__listener_net_status = listener

    def stop_status_listener(self):
        """Stops the NetStatusListener from listening to the drive."""
        if self.__listener_net_status is not None:
            self.__listener_net_status.stop()
            self.__listener_net_status.join()
        self.__listener_net_status = None

    def _notify_status(self, ip, status):
        """Notify subscribers of a network state change."""
        for callback in self.__observers_net_state[ip]:
            callback(status)

    def subscribe_to_status(self, ip, callback):
        """Subscribe to network state changes.

        Args:
            ip (str): IP of the drive to subscribe.
            callback (function): Callback function.

        """
        if callback in self.__observers_net_state[ip]:
            logger.info("Callback already subscribed.")
            return
        self.__observers_net_state[ip].append(callback)

    def unsubscribe_from_status(self, ip, callback):
        """Unsubscribe from network state changes.

        Args:
            ip (str): IP of the drive to unsubscribe.
            callback (function): Callback function.

        """
        if callback not in self.__observers_net_state[ip]:
            logger.info("Callback not subscribed.")
            return
        self.__observers_net_state[ip].remove(callback)

    def _get_servo_state(self, ip):
        return self.__servos_state[ip]

    def _set_servo_state(self, ip, state):
        self.__servos_state[ip] = state

    @property
    def protocol(self):
        """NET_PROT: Obtain network protocol."""
        return NET_PROT.ETH
