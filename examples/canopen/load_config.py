import sys
from ingenialink.canopen.net import Network, CAN_DEVICE
import os

def run_example(eds_path, dict_path, config_path):
    net = None
    try:
        net = Network(device=CAN_DEVICE.PCAN)
        # net = Network(device=CAN_DEVICE.KVASER)
        net.scan(eds_path, dict_path)
        drives_connected = net.servos
        if len(drives_connected) > 0:
            drive = drives_connected[0]
            drive.dict_storage_write(config_path)
            print("Configuration loaded correctly!")
        else:
            print("No drives found! Disconnecting from the network...")
        net.disconnect()
    except Exception as e:
        print(e)
        net.disconnect()
if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("load_config.exe C:/path/to/eds_file.eds C:/path/to/dictionary.xdf C:/path/to/configuration.xcf")

    else:
        eds_path = sys.argv[1]
        dict_path = sys.argv[2]
        config_path = sys.argv[3]
        test = run_example(eds_path, dict_path, config_path)
    sys.exit()