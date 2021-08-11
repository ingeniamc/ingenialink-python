from ..network import Network, NET_PROT, NET_TRANS_PROT, NET_DEV_EVT, NET_STATE
from .servo import EthernetServo
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


class EthernetNetwork(Network):
    def __init__(self):
        super(EthernetNetwork, self).__init__()
        self.__cffi_network = None

    @classmethod
    def _from_existing(cls, net):
        """ Create a new class instance from an existing network.

        Args:
            net (Network): Instance to copy.

        Returns:
            Network: New instanced class.

        """
        inst = cls.__new__(cls)
        inst.__cffi_network = ffi.gc(net, lib.il_net_fake_destroy)
        return inst

    @staticmethod
    def load_firmware(fw_file, target="192.168.2.22", ftp_user="", ftp_pwd=""):
        """ Loads a given firmware file to the target slave.

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

    def load_firmware_moco(node, subnode, ip, port, moco_file):
        """
        Update MOCO firmware through UDP protocol.
        Args:
            node: Network node.
            subnode: Drive subnode.
            ip: Drive address IP.
            port: Drive port.
            moco_file: Path to the firmware file.
        Returns:
            int: Result code.
        """
        r = 1
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
        """ Connects to a slave through the given network settings.

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

        net = self._from_existing(net_)
        servo = EthernetServo._from_existing(servo_, _dictionary)
        servo.net = net
        servo.target = target
        servo._dictionary = dictionary
        servo.port = port
        servo.communication_protocol = communication_protocol

        self.servos.append(servo)

        return servo

    def disconnect_from_slave(self, servo):
        """ Disconnects the slave from the network.

        Args:
            servo (EthernetServo): Instance of the servo connected.
        """
        # TODO: This stops all connections no only the target servo.
        self.servos.remove(servo)
        if len(self.servos) == 0:
            self.stop_network_monitor()
            self.close_socket()

    def close_socket(self):
        """ Closes the established network socket. """
        return lib.il_net_close_socket(self.__cffi_network)

    def destroy_network(self):
        """ Destroy network instance. """
        lib.il_net_destroy(self.__cffi_network)

    def subscribe_to_network_status(self, on_evt):
        """ Calls given function everytime a connection/disconnection event is
        raised.

        Args:
            on_evt (Callback): Function that will be called every time an event
            is raised.
        """
        status = self.status
        while True:
            if status != self.status:
                if self.status == 0:
                    on_evt(NET_DEV_EVT.ADDED)
                elif self.status == 1:
                    on_evt(NET_DEV_EVT.REMOVED)
                status = self.status
            sleep(1)

    def stop_network_monitor(self):
        """ Stop monitoring network events. """
        lib.il_net_mon_stop(self.__cffi_network)

    def set_reconnection_retries(self, retries):
        """ Set the number of reconnection retries in our application.

        Args:
            retries (int): Number of reconnection retries.
        """
        return lib.il_net_set_reconnection_retries(self.__cffi_network, retries)

    def set_recv_timeout(self, timeout):
        """ Set receive communications timeout.

        Args:
            timeout (int): Timeout in ms.
        Returns:
            int: Result code.
        """
        return lib.il_net_set_recv_timeout(self.__cffi_network, timeout)

    def set_status_check_stop(self, stop):
        """ Start/Stop the internal monitor of the drive status.

        Args:
            stop (int): 0 to START, 1 to STOP.
        Returns:
            int: Result code.
        """
        return lib.il_net_set_status_check_stop(self.__cffi_network, stop)

    @property
    def protocol(self):
        """ NET_PROT: Obtain network protocol. """
        return NET_PROT.ETH

    @property
    def _cffi_network(self):
        """ Obtain network CFFI instance. """
        return self.__cffi_network

    @_cffi_network.setter
    def _cffi_network(self, value):
        """ Set network CFFI instance. """
        self.__cffi_network = value

    @property
    def state(self):
        """ Obtain network state.

        Returns:
            str: Current network state.
        """
        return NET_STATE(lib.il_net_state_get(self.__cffi_network))

    @property
    def status(self):
        """ Obtain network status.

        Returns:
            str: Current network status.
        """
        return lib.il_net_status_get(self.__cffi_network)
