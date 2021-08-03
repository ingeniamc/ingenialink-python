from ..net import Network, NET_PROT, NET_TRANS_PROT
from .eth_servo import EthernetServo
from .._utils import cstr, pstr, raise_null, raise_err, to_ms
from .._ingenialink import lib, ffi

from ftplib import FTP
from os import system, remove

FTP_SESSION_OK_CODE = "220"
FTP_LOGIN_OK_CODE = "230"
FTP_FILE_TRANSFER_OK_CODE = "226"
FTP_CLOSE_OK_CODE = "221"


class FtpUploadTracker:
    size_written = 0
    total_size = 0
    block_size = 0
    last_percentage = 0

    def __init__(self, total_size, block_size):
        self.size_written = 0
        self.total_size = total_size
        self.block_size = block_size
        self.last_percentage = 0

    def handle(self, _):
        self.size_written += self.block_size
        percent_complete = round((self.size_written / self.total_size) * 100)
        if self.last_percentage != percent_complete:
            self.last_percentage = percent_complete
            print("{} % complete\n".format(str(percent_complete)))


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

    def load_fw(self, fw_file, target="192.168.2.22", ftp_user="Ingenia", ftp_pwd="Ingenia"):
        print("Flash FW: FTP")
        try:
            user = ftp_user
            pwd = ftp_pwd

            file = open(fw_file, 'rb')
            ftp_output = None
            ftp = FTP()

            # Start a FTP session. Drive must be in BOOT mode.
            if not self.msg:
                ftp_output = ftp.connect(target)
                print(ftp_output)
                if FTP_SESSION_OK_CODE not in ftp_output:
                    raise_err("Unable to open FTP session")

                # Login into FTP session.
                if not self.msg:
                    ftp_output = ftp.login(user, pwd)
                    print(ftp_output)
                    if FTP_LOGIN_OK_CODE not in ftp_output:
                        raise_err("Unable to login the FTP session")

                # Load file through FTP.
                if not self.msg:
                    ftp.set_pasv(
                        False)  # This command does not return any output
                    ftp_output = ftp.storbinary(
                        "STOR {}".format(file), file)
                    print(ftp_output)
                    if FTP_FILE_TRANSFER_OK_CODE not in ftp_output:
                        raise_err(
                            "Unable to load the FW file through FTP")

                # Close FTP session.
                if not self.msg:
                    try:
                        ftp_output = ftp.quit()
                        print(ftp_output)
                        if FTP_CLOSE_OK_CODE not in ftp_output:
                            raise_err(
                                "Unable to close the FTP session")
                    except Exception as e:
                        print("Expected when flashing CoCo: {}".format(e))
                        ftp_output = ftp.close()  # This command does not return any output

                # Close the temporal file
                file.close()
                remove(self.temp_path)

        except Exception as e:
            self.add_error("Exception when flashing drive: {}".format(e))

        # Wait until FW is programmed (check Com-Kit LEDs)
        if not self.msg:
            try:
                title = "Programming FW"
                description = "Please wait until ETH LED of Com-Kit turns OFF\n" \
                              "and only GREEN LED (+5V) remains ON"
                self.interface.ask_done(title, description)
                print(
                    "Firmware flashed into drive. Done.                     \n")
            except Exception as e:
                self.add_error(
                    "Exception when flashing firmware into DUT: {}".format(e))

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
