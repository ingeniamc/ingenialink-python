import sys
from time import sleep

import ingenialink as il

def on_evt(evt):
    print(evt)

# XCORE
def run_example_eth_monitor():
    protocol = il.NET_PROT.ETH
    ip = "192.168.2.5"
    net, servo = il.lucky(protocol, "xcore-enums.xml", ip)

    net.net_mon_status(on_evt)

    while True:
        sleep(0.5)


if __name__ == '__main__':
    test = run_example_eth_monitor()
    sys.exit()