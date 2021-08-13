import sys
from time import sleep
import ingenialink as il


def scan_port(drives, protocol, port):
    new_drives = drives
    try:
        network_in_use = False
        for drive in new_drives:
            if drive['network'].prot == protocol and \
                    drive['network'].port == port:
                network_in_use = True
        if not network_in_use:
            network = il.Network(protocol, port)
            sleep(0.1)
            drives_detected = network.servos()
            for drive in drives_detected:
                new_drives.append({"port": port,
                                   "drive": drive,
                                   "network": network,
                                   "protocol": protocol})
    except Exception as e:
        pass
    return new_drives


def mcb_scan_drives():
    protocol = il.NET_PROT.MCB
    drives = []
    while True:
        ports_to_scan = il.devices(protocol)
        for port in ports_to_scan:
            drives = scan_port(drives, protocol, port)
        print(drives)
        sleep(1)


if __name__ == '__main__':
    mcb_scan_drives()
    sys.exit()