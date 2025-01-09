import ftplib
import os
import socket
import time
from collections import OrderedDict, defaultdict
from ftplib import FTP
from threading import Thread
from time import sleep
from typing import Any, Callable, Optional, Union

import ingenialogger

from ingenialink.constants import DEFAULT_ETH_CONNECTION_TIMEOUT
from ingenialink.exceptions import ILError, ILFirmwareLoadError
from ingenialink.network import NET_DEV_EVT, NET_PROT, NET_STATE, Network, SlaveInfo
from ingenialink.utils.udp import UDP

from .servo import EthernetServo

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
        network: Network instance of the Ethernet communication.

    """

    def __init__(self, network: "EthernetNetwork", refresh_time: float = 0.25) -> None:
        super().__init__()
        self.__network = network
        self.__refresh_time = refresh_time
        self.__stop = False
        self.__max_unsuccessful_pings = MAX_NUM_UNSUCCESSFUL_PINGS

    def run(self) -> None:
        """Check the network status."""
        while not self.__stop:
            for servo in self.__network.servos:
                unsuccessful_pings = 0
                servo_ip = servo.ip_address
                servo_state = self.__network.get_servo_state(servo_ip)
                while unsuccessful_pings < self.__max_unsuccessful_pings:
                    response = servo.is_alive()
                    if not response:
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
            time.sleep(self.__refresh_time)

    def stop(self) -> None:
        """Stop the listener."""
        self.__stop = True


class EthernetNetwork(Network):
    """Network for all Ethernet communications."""

    def __init__(self) -> None:
        super().__init__()
        self.__listener_net_status: Optional[NetStatusListener] = None
        self.__observers_net_state: dict[str, list[Callable[[NET_DEV_EVT], Any]]] = defaultdict(
            list,
        )

    @staticmethod
    def load_firmware(
        fw_file: str,
        target: str = "192.168.2.22",
        ftp_user: str = "",
        ftp_pwd: str = "",
    ) -> None:
        """Loads a given firmware file to the target slave.

        .. warning ::
            It is needed to disconnect the drive(:func:`disconnect_from_slave`)
            after loading the firmware since the `Servo` object's data will
            become obsolete.

        Args:
            fw_file: Path to the firmware file to be loaded.
            target: IP of the target slave.
            ftp_user: FTP user to connect with.
            ftp_pwd: FTP password for the given user.

        Raises:
            ILError: If the loading firmware process fails.

        """
        if not os.path.isfile(fw_file):
            msg = f"Could not find {fw_file}."
            raise FileNotFoundError(msg)

        # Start a FTP session. Drive must be in BOOT mode.
        logger.info("Starting FTP session...")
        with FTP() as ftp:  # noqa: S321
            try:
                ftp_output = ftp.connect(target)
            except ConnectionError as e:
                msg = "Unable to create the FTP session"
                raise ILFirmwareLoadError(msg) from e
            logger.info(ftp_output)
            if FTP_SESSION_OK_CODE not in ftp_output:
                msg = "Unable to open the FTP session"
                raise ILFirmwareLoadError(msg)
            # Login into FTP session.
            logger.info("Logging into FTP session...")
            ftp_output = ftp.login(ftp_user, ftp_pwd)
            logger.info(ftp_output)
            if FTP_LOGIN_OK_CODE not in ftp_output:
                msg = "Unable to login the FTP session"
                raise ILFirmwareLoadError(msg)
            # Load file through FTP.
            logger.info("Uploading firmware file...")
            ftp.set_pasv(False)
            with open(fw_file, "rb") as file:
                ftp_output = ftp.storbinary(f"STOR {os.path.basename(file.name)}", file)
            logger.info(ftp_output)
            if FTP_FILE_TRANSFER_OK_CODE not in ftp_output:
                msg = "Unable to load the FW file through FTP"
                raise ILFirmwareLoadError(msg)
        logger.info("FTP session closed.")

    @staticmethod
    def load_firmware_moco(node: int, subnode: int, ip: str, port: int, moco_file: str) -> None:
        """Update MOCO firmware through UDP protocol.

        Args:
            node: Network node.
            subnode: Drive subnode.
            ip: Drive address IP.
            port: Drive port.
            moco_file: Path to the firmware file.

        Returns:
            Result code.

        Raises:
            ILFirmwareLoadError: The firmware load process fails
                with an error message.
        """
        upd = UDP(port, ip)

        if not moco_file or not os.path.isfile(moco_file):
            msg = "File not found"
            raise ILFirmwareLoadError(msg)

        with open(moco_file) as moco_in:
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
                logger.exception("Error loading firmware.")
                msg = "Firewall might be blocking the access."
                raise ILFirmwareLoadError(msg) from e
            except Exception as e:
                logger.exception("Error loading firmware.")
                msg = "Error during bootloader process."
                raise ILFirmwareLoadError(msg) from e

    def scan_slaves(self) -> list[int]:  # noqa: D102
        raise NotImplementedError

    def scan_slaves_info(self) -> OrderedDict[int, SlaveInfo]:  # noqa: D102
        raise NotImplementedError

    def connect_to_slave(
        self,
        target: str,
        dictionary: str,
        port: int = 1061,
        connection_timeout: float = DEFAULT_ETH_CONNECTION_TIMEOUT,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
        is_eoe: bool = False,
    ) -> EthernetServo:
        """Connects to a slave through the given network settings.

        Args:
            target: IP of the target slave.
            dictionary: Path to the target dictionary file.
            port: Port to connect to the slave.
            connection_timeout: Time in seconds of the connection timeout.
            servo_status_listener: Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener: Toggle the listener of the network
                status, connection and disconnection.
            is_eoe: True if communication is EoE. ``False`` by default.

        Returns:
            EthernetServo: Instance of the servo connected.

        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(connection_timeout)
        sock.connect((target, port))
        servo = EthernetServo(sock, dictionary, servo_status_listener, is_eoe)
        try:
            servo.get_state()
        except ILError as e:
            servo.stop_status_listener()
            msg = f"Drive not found in IP {target}."
            raise ILError(msg) from e
        self.servos.append(servo)
        self._set_servo_state(target, NET_STATE.CONNECTED)

        if net_status_listener:
            self.start_status_listener()
        else:
            self.stop_status_listener()

        return servo

    def disconnect_from_slave(self, servo: EthernetServo) -> None:  # type: ignore [override]
        """Disconnects the slave from the network.

        Args:
            servo: Instance of the servo connected.

        """
        self.servos.remove(servo)
        servo.stop_status_listener()
        self.close_socket(servo.socket)
        self._set_servo_state(servo.ip_address, NET_STATE.DISCONNECTED)
        if len(self.servos) == 0:
            self.stop_status_listener()

    @staticmethod
    def close_socket(sock: socket.socket) -> None:
        """Closes the established network socket."""
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()

    def start_status_listener(self) -> None:
        """Start monitoring network events (CONNECTION/DISCONNECTION)."""
        if self.__listener_net_status is None:
            listener = NetStatusListener(self)
            listener.start()
            self.__listener_net_status = listener

    def stop_status_listener(self) -> None:
        """Stops the NetStatusListener from listening to the drive."""
        if self.__listener_net_status is not None:
            self.__listener_net_status.stop()
            self.__listener_net_status.join()
        self.__listener_net_status = None

    def _notify_status(self, ip: str, status: NET_DEV_EVT) -> None:
        """Notify subscribers of a network state change."""
        for callback in self.__observers_net_state[ip]:
            callback(status)

    def subscribe_to_status(self, ip: str, callback: Callable[[NET_DEV_EVT], Any]) -> None:  # type: ignore [override]
        """Subscribe to network state changes.

        Args:
            ip: IP of the drive to subscribe.
            callback: Callback function.

        """
        if callback in self.__observers_net_state[ip]:
            logger.info("Callback already subscribed.")
            return
        self.__observers_net_state[ip].append(callback)

    def unsubscribe_from_status(self, ip: str, callback: Callable[[NET_DEV_EVT], Any]) -> None:  # type: ignore [override]
        """Unsubscribe from network state changes.

        Args:
            ip: IP of the drive to unsubscribe.
            callback: Callback function.

        """
        if callback not in self.__observers_net_state[ip]:
            logger.info("Callback not subscribed.")
            return
        self.__observers_net_state[ip].remove(callback)

    def get_servo_state(self, servo_id: Union[int, str]) -> NET_STATE:
        """Get the state of a servo that's a part of network.

        The state indicates if the servo is connected or disconnected.

        Args:
            servo_id: The servo's IP address.

        Returns:
            The servo's state.

        """
        if not isinstance(servo_id, str):
            msg = "The servo ID must be a string."
            raise TypeError(msg)
        return self._servos_state[servo_id]

    def _set_servo_state(self, servo_id: Union[int, str], state: NET_STATE) -> None:
        """Set the state of a servo that's a part of network.

        Args:
            servo_id: The servo's IP address.
            state: The servo's state.

        """
        self._servos_state[servo_id] = state

    @property
    def protocol(self) -> NET_PROT:
        """Obtain network protocol."""
        return NET_PROT.ETH
