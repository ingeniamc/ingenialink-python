import sys

from ingenialink.ethercat.network import EthercatNetwork


def ecat_load_fw():
    net = EthercatNetwork("\\Device\\NPF_{192D1D2F-C684-467D-A637-EC07BD434A63}")

    net.load_firmware(fw_file='../../resources/firmware/cap-net-e_0.7.1.lfu',
                      boot_in_app=True)


if __name__ == '__main__':
    ecat_load_fw()
    sys.exit(0)
