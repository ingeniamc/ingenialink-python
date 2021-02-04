import sys

import ingenialink as il


def load_save_config():
    # Connection
    servo = None
    try:
        _, servo = il.lucky(il.NET_PROT.ETH, "summit.xml", address_ip='192.168.2.22', port_ip=1061, protocol=2)
    except Exception as e:
        print("Error trying to connect to the servo.", str(e))
    if servo is not None:
        # Get the current drive config
        servo.dict_storage_read()
        new_dict = servo.dict
        new_dict.save('new_dict.xml')
        print("new_dict.xml created")
        # Load and save it again to the drive
        servo.dict_load('new_dict.xml')
        servo.dict_storage_write()
        print("new_dict.xml loaded")


if __name__ == '__main__':
    load_save_config()
    sys.exit(0)
