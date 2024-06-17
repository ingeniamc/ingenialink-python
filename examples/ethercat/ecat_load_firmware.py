import sys

from ingenialink.ethercat.network import EthercatNetwork


def ecat_load_fw() -> None:
    net = EthercatNetwork("\\Device\\NPF_{192D1D2F-C684-467D-A637-EC07BD434A63}")

    # Set boot_in_app to True if the firmware file is of type .sfu
    # It is important to set this parameter carefully as an incorrect configuration can cause the
    # drive to become non-functional!
    boot_in_app = False

    net.load_firmware(
        fw_file="../../resources/firmware/cap-net-e_0.7.1.lfu", boot_in_app=boot_in_app
    )


if __name__ == "__main__":
    ecat_load_fw()
    sys.exit(0)
