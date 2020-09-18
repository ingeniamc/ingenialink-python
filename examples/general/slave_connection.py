import sys

import ingenialink as il


def slave_connection():
    # Connection
    servo = None
    # r = il.servo.servo_is_connected("192.168.2.22", port_ip=1061, protocol=2)
    # print("Result: ", r)
    # return r
    try:
        net, servo = il.lucky(il.NET_PROT.ETH, "eve-net_1.6.1.xdf", address_ip='192.168.2.22', port_ip=1061, protocol=1)

        # print(r)
        print("GAS")
    except Exception as e:
        print("Error trying to connect to the servo.", str(e))
    if servo is not None:
        regg = servo.dict.get_regs(1)['COMMU_ANGLE_OFFSET']
        print(servo.dict.subnodes)
        print('COMMU_ANGLE_OFFSET 1:',
              servo.raw_read('COMMU_ANGLE_OFFSET', subnode=1))
        print(servo.dict.get_regs(1)['COMMU_ANGLE_OFFSET'].range)
        print('CL_CUR_B_REF_VALUE 1:',
              servo.raw_read('CL_CUR_B_REF_VALUE', subnode=1), 'A')
        print(servo.dict.get_regs(1)['CL_CUR_B_REF_VALUE'].range)
        print('CL_VEL_REF_VALUE 1:',
              servo.raw_read('CL_VEL_REF_VALUE', subnode=1), 'A')
        print(servo.dict.get_regs(1)['CL_VEL_REF_VALUE'].range)

        # Try to write and read a register
        # try:
        #     servo.enable()
        #     servo.write('COMMU_ANGLE_SENSOR', 3)
        # except Exception as e:
        #     print(e)

        # print('COMMU_ANGLE_SENSOR:', servo.read('COMMU_ANGLE_SENSOR'))


if __name__ == '__main__':
    slave_connection()
    sys.exit(0)
