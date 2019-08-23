import sys
from time import sleep

import ingenialink as il


def scan_port(drives, protocol, port, timeout, ip):
    new_drives = drives
    try:
        network_in_use = False
        for drive in new_drives:
            if drive['network'].prot == protocol and drive['network'].port == port:
                network_in_use = True
        if not network_in_use:
            network = il.Network(protocol, port)
            sleep(0.1)
            drives_detected = network.servos()
            for drive in drives_detected:
                new_drives.append({"port": port, "drive": drive, "network": network, "protocol": protocol})
    except:
        pass
    return new_drives

# XCORE
def run_example_scan():
    protocol = il.NET_PROT.MCB
    drives = []
    while True:
        ports_to_scan = il.devices(protocol)
        for port in ports_to_scan:
            drives = scan_port(drives, protocol, port, 0, None)
        print(drives)
        sleep(1)


if __name__ == '__main__':
    test = run_example_scan()

    sys.exit()