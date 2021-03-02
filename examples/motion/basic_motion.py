import ingenialink as il
import numpy as np
import argparse
from time import sleep
import threading


CSV_MODE = 35
CSP_MODE = 36

stop_thread = False
sampling_time = 0.1


def read_thread(servo, actual_val_reg_id):
    global stop_thread
    while not stop_thread:
        print("Actual value: ", servo.read(actual_val_reg_id))


def slave_connection(ip):
    servo = None
    try:
        _, servo = il.lucky(il.NET_PROT.ETH,
                            "resources/eve-net_1.7.1.xdf",
                            address_ip=ip,
                            port_ip=1061,
                            protocol=2)
    except Exception as e:
        print("There was an error while scanning the network")
    return servo


def basic_motion(args):
    servo = slave_connection(args.ip)
    if servo is None:
        print("Cannot find any slave connected.")
        return -1
    else:
        print("Slave found!")
        # Obtain arguments
        if args.op == 'CSV':
            op_mode = CSV_MODE
            target_reg_id = 'CL_VEL_SET_POINT_VALUE'
            actual_val_reg_id = 'FBK_CUR_MODULE_VALUE'
            multiplier = 10
        else:
            op_mode = CSP_MODE
            target_reg_id = 'CL_POS_SET_POINT_VALUE'
            actual_val_reg_id = 'CL_POS_FBK_VALUE'
            multiplier = 1000

        # Set Operation Mode
        servo.write('DRV_OP_CMD', op_mode)

        # Generate an slow sine wave of 10 seconds
        time = np.arange(0, 10, sampling_time)
        amplitude = np.sin(time)
        print("Amplitude: ", amplitude)

        # Enable motor
        try:
            servo.enable()
        except:
            print("Cannot enable the motor")
            return -2

        # Start reading thread
        thread = threading.Thread(target=read_thread, args=(servo, actual_val_reg_id))
        thread.start()

        # Send the generated targets
        for value in amplitude:
            print("Target demanded: ", value*multiplier)
            servo.write(target_reg_id, int(value*multiplier))
            sleep(sampling_time)

        # Stop the reading thread
        global stop_thread
        stop_thread = True
        thread.join()

        # Disable motor
        try:
            servo.disable()
        except:
            print("Cannot disable the motor")
            return -2
        return 0


if __name__ == '__main__':
    # Usage
    parser = argparse.ArgumentParser(description='Basic Motion Application.')
    parser.add_argument('--ip', metavar="", type=str, help='the ip of the drive. 192.168.2.22 by default',
                        default='192.168.2.22')
    parser.add_argument('--op', metavar="", type=str, help='Operation mode to use [CSP, CSV]',
                        default='CSP')
    args = parser.parse_args()
    basic_motion(args)