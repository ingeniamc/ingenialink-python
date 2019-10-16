import sys

from ingenialink.canopen.net import Network, CAN_DEVICE

def run_example():
    net = Network(device=CAN_DEVICE.PCAN)
    net.scan('eve-net_canopen_1.4.2.eds')

if __name__ == '__main__':
    test = run_example()

    sys.exit()