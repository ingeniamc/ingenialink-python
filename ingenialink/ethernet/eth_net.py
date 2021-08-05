from ..net import Network, NET_PROT, NET_TRANS_PROT
from .eth_servo import EthernetServo
from ingenialink.utils._utils import cstr, pstr, raise_null, raise_err, to_ms
from .._ingenialink import lib, ffi
import ingenialogger




from ftplib import FTP
from os import system, remove, path

FTP_SESSION_OK_CODE = "220"
FTP_LOGIN_OK_CODE = "230"
FTP_FILE_TRANSFER_OK_CODE = "226"
FTP_CLOSE_OK_CODE = "221"

logger = ingenialogger.get_logger(__name__)


class EthernetNetwork(Network):
    def __init__(self):
        self.__net = None
        self.msg = ""
        opts = ffi.new('il_net_opts_t *')
        self._net = lib.il_net_create(NET_PROT.ETH.value, opts)
        raise_null(self._net)

    def add_error(self, error_msg):
        if not self.msg:
            self.msg = error_msg
        else:
            self.msg = "{}\n{}".format(self.msg, error_msg)
        print(error_msg)

    def load_firmware(self, fw_file, target="192.168.2.22", ftp_user="", ftp_pwd=""):
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

    def scan_nodes(self):
        raise NotImplementedError

    def connect_to_slave(self, target, dictionary=None, port=1061,
                communication_protocol=NET_TRANS_PROT.UDP):
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

        net = Network._from_existing(net_)
        servo = EthernetServo._from_existing(servo_, _dictionary)
        servo.net = net
        servo.target = target
        servo.dictionary = dictionary
        servo.port = port
        servo.communication_protocol = communication_protocol

        self.__net = net
        self.servos.append(servo)

        return r, servo

    def disconnect_from_slave(self, servo):
        raise NotImplementedError

    # Properties
    @property
    def net(self):
        return self.__net

    @net.setter
    def net(self, value):
        self.__net = value
