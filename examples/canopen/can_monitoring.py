import sys
import numpy as np
from ingenialink.canopen.network import CanopenNetwork, CAN_DEVICE, CAN_BAUDRATE
from ingenialink.constants import data_type_size
from ingenialink.ethercat.network import EthercatNetwork


def monitoring_example():
    registers_key = [
        "DRV_PROT_TEMP_VALUE",
    ]

    #net = CanopenNetwork(device=CAN_DEVICE.PCAN,
    #                     channel=0,
    #                     baudrate=CAN_BAUDRATE.Baudrate_1M)
    #nodes = net.scan_slaves()
    #servo = net.connect_to_slave(
    #    target=nodes[0],
    #    dictionary="C://Users//martin.acosta//Documents//issues//INGK-672//evs-net-c_can_2.4.1")
    net = EthercatNetwork(r'\Device\NPF_{43144EC3-59EF-408B-8D9B-4867F1324D62}')
    slave_id = net.scan_slaves()
    slave_id = slave_id[0]
    servo = net.connect_to_slave(slave_id, "C://Users//martin.acosta//Documents//issues//INGK-672//evs-net-c_can_2.4.1.xdf")
    # Monitoring
    # Remove all mapped registers
    servo.monitoring_disable()
    servo.monitoring_remove_all_mapped_registers()

    # Calculate the monitoring frequency
    ccp_value = 12
    servo.write('MON_DIST_FREQ_DIV', ccp_value, subnode=0)
    position_velocity_loop_rate = servo.read(
        'DRV_POS_VEL_RATE'
    )
    sampling_freq = round(
        position_velocity_loop_rate / ccp_value, 2
    )

    read_process_finished = False
    tmp_mon_data = []
    monitor_data = []

    for idx, key in enumerate(registers_key):
        mapped_reg = servo.dictionary.registers(1)[key].idx
        dtype = servo.dictionary.registers(1)[key].dtype.value
        servo.monitoring_set_mapped_register(
            idx, mapped_reg, 1, dtype, 4
        )
        tmp_mon_data.append([])
        monitor_data.append([])
    # Configure monitoring SOC as forced
    servo.write('MON_CFG_SOC_TYPE', 0, subnode=0)
    # Configure monitoring EoC as number of samples
    servo.write('MON_CFG_EOC_TYPE', 3, subnode=0)
    # Configure number of samples
    window_samples = 599
    total_num_samples = window_samples
    servo.write('MON_CFG_WINDOW_SAMP', window_samples, subnode=0)
    # Enable monitoring
    servo.monitoring_enable()
    # Check monitoring status
    monitor_status = servo.read('MON_DIST_STATUS', subnode=0)
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
            monit_nmb_blocks = servo.read(
                'MON_CFG_CYCLES_VALUE',
                subnode=0
            )
            if monit_nmb_blocks > 0:
                servo.monitoring_read_data()
                for idx, key in enumerate(registers_key):
                    index = idx
                    dtype = servo.dictionary.registers(1)[key].dtype
                    tmp_monitor_data = servo. \
                        monitoring_channel_data(index)
                    tmp_mon_data[index] = \
                        tmp_mon_data[index] + tmp_monitor_data
                    if len(tmp_mon_data[index]) >= total_num_samples:
                        tmp_mon_data[index] = np.resize(
                            tmp_mon_data[index], total_num_samples
                        )
                        data_x = np.arange(
                            (window_samples) * sampling_time_s,
                            sampling_time_s
                        )

                        if data_x.size > len(tmp_mon_data[index]):
                            data_x = np.resize(
                                data_x, len(tmp_mon_data[index])
                            )
                        data_y = tmp_mon_data[index]
                        monitor_data[index] = np.round(data_y, decimals=2)
                        data_obtained = True
                if data_obtained:
                    # Single-shot mode
                    read_process_finished = True
        except Exception as e:
            print('Exception monitoring: {}'.format(e))
            break
    print("Finished")
    print(len(monitor_data), np.unique(monitor_data))
    net.disconnect_from_slave(servo)


if __name__ == '__main__':
    monitoring_example()
    sys.exit(0)
