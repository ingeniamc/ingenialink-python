import sys
from time import time, sleep
import ingenialink as il


def ecat_load_fw():
    # FOE Bootloader
    r = il.network.update_firmware("\\Device\\NPF_{E8228BC6-D9E5-4CD0-BCDC-A9023F7977B3}",
                               "resources/eve-net_ecat_1.7.1.sfu",
                                   slave=1,
                                   is_summit=True)


if __name__ == '__main__':
    ecat_load_fw()
    sys.exit(0)
