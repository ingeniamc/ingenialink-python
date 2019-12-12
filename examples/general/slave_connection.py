import sys

import ingenialink as il


def slave_connection():
    # Connection
    servo = None
    try:
        _, servo = il.lucky(il.NET_PROT.ETH, "summit.xml", address_ip='192.168.2.22', port_ip=1061)
    except Exception as e:
        print("Error trying to connect to the servo.", str(e))
    if servo is not None:
        # Try to write and read a register
        servo.write('BRAKE_PRE_DELAY', 100)
        print('BRAKE_PRE_DELAY:', servo.read('BRAKE_PRE_DELAY'), 'ms')
        servo.write('BRAKE_PRE_DELAY', 0)
        print('BRAKE_PRE_DELAY:', servo.read('BRAKE_PRE_DELAY'), 'ms')


if __name__ == '__main__':
    slave_connection()
    sys.exit(0)
