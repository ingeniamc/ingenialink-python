import sys
import numpy as np
from ingenialink.ethernet.network import EthernetNetwork, NET_TRANS_PROT
from ingenialink.ethercat.network import EthercatNetwork


def monitoring_example():
    registers_key = [
        "DRV_PROT_TEMP_VALUE",
    ]

    net = EthercatNetwork(
        interface_name="\\Device\\NPF_{13C5D891-C81E-46CE-8651-FADBE3C9415D}")
    servo = net.connect_to_slave(
        target=1,
        dictionary='../../resources/dictionaries/eve-xcr-e_eoe_1.8.1.xdf')
    # Monitoring
    # Remove all mapped registers
    servo.monitoring_disable()
    servo.monitoring_remove_all_mapped_registers()

    # Calculate the monitoring frequency
    ccp_value = 10
    servo.write('MON_DIST_FREQ_DIV', ccp_value, subnode=0)
    position_velocity_loop_rate = servo.raw_read(
        'DRV_POS_VEL_RATE'
    )
    sampling_freq = round(
        position_velocity_loop_rate / ccp_value, 2
    )

    read_process_finished = False
    tmp_mon_data = []
    monitor_data = []
    # if add_time:
    #     monitor_data.append([])
    for idx, key in enumerate(registers_key):
        mapped_reg = servo.dictionary.registers(1)[key].address
        dtype = servo.dictionary.registers(1)[key].dtype.value
        servo.monitoring_set_mapped_register(
            idx, mapped_reg, dtype
        )
        tmp_mon_data.append([])
        monitor_data.append([])
    servo.write('MON_CFG_TRIGGER_REPETITIONS', 1, subnode=0)
    # Configure monitoring SOC as forced
    servo.write('MON_CFG_SOC_TYPE', 0, subnode=0)
    # Configure monitoring EoC as number of samples
    servo.write('MON_CFG_EOC_TYPE', 3, subnode=0)
    # Configure number of samples
    tg_delay_samples = 1
    window_samples = 599
    total_num_samples = tg_delay_samples + window_samples
    servo.write('MON_CFG_TRIGGER_DELAY', tg_delay_samples, subnode=0)
    servo.write('MON_CFG_WINDOW_SAMP', window_samples, subnode=0)
    # servo.disable()
    # Enable monitoring
    servo.monitoring_enable()
    # servo.enable()
    # Check monitoring status
    monitor_status = servo.raw_read('MON_DIST_STATUS', subnode=0)
    if (monitor_status & 0x1) != 1:
        print("ERROR MONITOR STATUS: ", monitor_status)
        return -1
    # Force Trigger
    servo.write('MON_CMD_FORCE_TRIGGER', 1, subnode=0)
    sampling_time_s = 1 / sampling_freq
    data_obtained = False

    # Start reading
    while not read_process_finished:
        try:
            monit_nmb_blocks = servo.raw_read(
                'MON_CFG_CYCLES_VALUE',
                subnode=0
            )
            if monit_nmb_blocks > 0:
                servo.monitoring_read_data()
                for idx, key in enumerate(registers_key):
                    index = idx
                    dtype = servo.dictionary.registers(1)[key].dtype
                    tmp_monitor_data = servo. \
                        monitoring_channel_data(index, dtype)
                    tmp_mon_data[index] = \
                        tmp_mon_data[index] + tmp_monitor_data
                    if len(tmp_mon_data[index]) >= total_num_samples:
                        tmp_mon_data[index] = np.resize(
                            tmp_mon_data[index], total_num_samples
                        )
                        data_x = np.arange(
                            -tg_delay_samples * sampling_time_s,
                            (window_samples) * sampling_time_s,
                            sampling_time_s
                        )

                        if data_x.size > len(tmp_mon_data[index]):
                            data_x = np.resize(
                                data_x, len(tmp_mon_data[index])
                            )
                        data_y = tmp_mon_data[index]
                        # if add_time:
                        #     if len(monitor_data[0]) == 0:
                        #         monitor_data[0] = np.round(data_x, decimals=4)
                        #     monitor_data[index + 1] = np.round(data_y,
                        #                                        decimals=2)
                        # else:
                        #     monitor_data[index] = np.round(data_y, decimals=2)
                        monitor_data[index] = np.round(data_y, decimals=2)
                        data_obtained = True
                if data_obtained:
                    # Single-shot mode
                    read_process_finished = True
        except Exception as e:
            print('Exception monitoring: {}'.format(e))
            break
    print("Finished")

    net.disconnect_from_slave(servo)
    return monitor_data

if __name__ == '__main__':
    monitoring_example()
    sys.exit(0)
