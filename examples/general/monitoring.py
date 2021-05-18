import sys
import numpy as np
from time import sleep

import ingenialink as il


def monitoring():
    # Connection
    servo = None
    try:
        _, servo = il.lucky(il.NET_PROT.ETH, "resources/eve-net_1.7.1.xdf",
                            address_ip='192.168.2.22',
                            port_ip=1061,
                            protocol=2)
    except Exception as e:
        print("Error trying to connect to the servo.", str(e))
    if servo is not None:
        # Stop previous monitoring instances
        servo.net.monitoring_disable()
        # Remove all previously mapped registers
        servo.net.monitoring_remove_all_mapped_registers()

        ccp_value = 10
        servo.write('MON_DIST_FREQ_DIV', ccp_value, subnode=0)

        servo.write('MON_CFG_TRIGGER_REPETITIONS', 1, subnode=0)
        # Configure monitoring SOC NO TRIGGER and EOC to the number of samples
        servo.write('MON_CFG_SOC_TYPE', 0, subnode=0)
        servo.write('MON_CFG_EOC_TYPE', 3, subnode=0)
        servo.write('MON_CFG_TRIGGER_DELAY', 1, subnode=0)
        servo.write('MON_CFG_WINDOW_SAMP', 1000, subnode=0)
        # Monitoring temperature readings
        monitoring_data = []
        mapped_reg = 0x0018
        dtype = 8
        servo.net.monitoring_set_mapped_register(0, mapped_reg, dtype)
        # Enable monitoring
        servo.net.monitoring_enable()
        # Check monitoring status
        monitor_status = servo.read('MON_DIST_STATUS', subnode=0)
        if (monitor_status & 0x1) != 1:
            print("ERROR MONITOR STATUS: ", monitor_status)
        read_process_finished = False
        first_data_entry = True
        servo.write('MON_CMD_FORCE_TRIGGER', 1, subnode=0)

        while not read_process_finished:
            try:
                monit_nmb_blocks = servo.read('MON_CFG_CYCLES_VALUE',
                                                  subnode=0)
                print("MON_CFG_CYCLES_VALUE ", monit_nmb_blocks)
                if not read_process_finished:
                    if first_data_entry:
                        max_data_value = monit_nmb_blocks
                        first_data_entry = False
                    servo.net.monitoring_read_data()
                    register = servo.dict.get_regs(1)['DRV_PROT_VBUS_VALUE'].dtype
                    tmp_monitor_data = servo.net.monitoring_channel_data(0, register)
                    monitoring_data = monitoring_data + tmp_monitor_data
                    if len(monitoring_data) >= 600:
                        np.resize(monitoring_data, 600)
                        read_process_finished = True
            except Exception as e:
                print("Error:", str(e))
        print("DRV_PROT_VBUS_VALUE:", monitoring_data)
        servo.net.monitoring_disable()


if __name__ == '__main__':
    monitoring()
    sys.exit(0)
