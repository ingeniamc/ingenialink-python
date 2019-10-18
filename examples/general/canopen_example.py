import sys

from ingenialink.canopen.net import Network, CAN_DEVICE

def run_example():
    net = None
    try:
        net = Network(device=CAN_DEVICE.PCAN)
        net.scan('eve-net_canopen_1.4.2.eds', 'eve-xcr_canopen.xml')
        drives_connected = net.servos
        if len(drives_connected) > 0:
            drive = drives_connected[0]
            while 1:
                try:
                    txt = input("Type the id of the register you want to read: ")
                    if txt == "exit":
                        break
                    print(txt + ": " + str(drive.raw_read(txt)))
                except Exception as e:
                    print(e)
        else:
            print("No drives found! Disconnecting from the network...")
        net.disconnect()
    except Exception as e:
        print(e)
        net.disconnect()
if __name__ == '__main__':
    test = run_example()

    sys.exit()