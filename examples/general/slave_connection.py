import sys
import ingenialink as il


def slave_connection():
    # Connection
    servo = None
    try:
        net, servo = il.lucky(il.NET_PROT.ETH,
                              "resources/eve-net_1.7.1.xdf",
                              address_ip='192.168.2.22',
                              port_ip=1061,
                              protocol=2)
    except Exception as e:
        print("Error trying to connect to the servo.", str(e))
    if servo is not None:
        # Try to write and read a register
        try:
            servo.write('COMMU_ANGLE_SENSOR', 3)
        except Exception as e:
            print(e)

        print('COMMU_ANGLE_SENSOR:', servo.read('COMMU_ANGLE_SENSOR'))


if __name__ == '__main__':
    slave_connection()
    sys.exit(0)
