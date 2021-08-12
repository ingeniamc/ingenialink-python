import sys
from ingenialink.ethernet.eth_net import EthernetNetwork


def ecat_load_fw():
    net = EthernetNetwork()

    net.load_firmware(fw_file='../../firmware/eve-net-c_1.8.1.sfu',
                      ftp_user='User', ftp_pwd='Password')


if __name__ == '__main__':
    ecat_load_fw()
    sys.exit(0)
