import sys
from ingenialink.ethernet.network import EthernetNetwork


def eth_load_fw():
    net = EthernetNetwork()

    net.load_firmware(fw_file='../../resources/firmware/eve-net-c_1.8.1.sfu',
                      ftp_user='Ingenia', ftp_pwd='Ingenia')


if __name__ == '__main__':
    eth_load_fw()
    sys.exit(0)
