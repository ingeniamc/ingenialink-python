import sys
import numpy as np
from time import sleep

import ingenialink as il


def monitoring():
    # Connection
    servo = None
    try:
        _, servo = il.lucky(il.NET_PROT.ETH, "summit.xml", address_ip='192.168.2.22', port_ip=1061)
    except Exception as e:
        print("Error trying to connect to the servo.", str(e))
    if servo is not None:
        # Configure monitoring parameters
        servo.net.monitoring_remove_all_mapped_registers()
        servo.write('MONITOR_TRIGGER_REPETITIONS', 1)
        # Configure monitoring SOC NO TRIGGER and EOC to the number of samples
        servo.write('MONITOR_SOC_TYPE', 0)
        servo.write('MONITOR_EOC_TYPE', 3)
        servo.write('MONITOR_TRIGGER_DELAY_SAMPLES', 1)
        servo.write('MONITOR_WINDOW_SAMPLES', 1000)
        # Monitoring temperature readings
        monitoring_data = []
        mapped_reg = servo.dict.regs['BUS_VOLTAGE_READINGS'].address
        dtype = servo.dict.regs['BUS_VOLTAGE_READINGS'].dtype.value
        servo.net.monitoring_set_mapped_register(0, mapped_reg, dtype)
        # Enable monitoring
        servo.net.monitoring_enable()
        # Check monitoring status
        monitor_status = servo.raw_read('CCP_STATUS')
        if (monitor_status & 0x1) != 1:
            print("ERROR MONITOR STATUS: ", monitor_status)
        read_process_finished = False
        first_data_entry = True
        while not read_process_finished:
            try:
                monit_nmb_blocks = servo.raw_read('MONITOR_NUMBER_CYCLES')
                print("MONITOR NUMBER BLOCKS ", monit_nmb_blocks)
                if not read_process_finished:
                    if first_data_entry:
                        max_data_value = monit_nmb_blocks
                        first_data_entry = False
                    servo.net.monitoring_read_data()
                    register = servo.dict.regs['BUS_VOLTAGE_READINGS'].dtype
                    tmp_monitor_data = servo.net.monitoring_channel_data(0, register)
                    monitoring_data = monitoring_data + tmp_monitor_data
                    if len(monitoring_data) >= 1001:
                        np.resize(monitoring_data, 1001)
                        read_process_finished = True
            except Exception as e:
                print("Error:", str(e))
        print("BUS_VOLTAGE_READINGS:", monitoring_data)
        servo.net.monitoring_disable()


if __name__ == '__main__':
    monitoring()
    sys.exit(0)
