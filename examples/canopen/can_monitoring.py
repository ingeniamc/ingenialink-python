import argparse
from typing import List

import numpy as np
from numpy.typing import NDArray

from ingenialink.canopen.network import CAN_BAUDRATE, CAN_DEVICE, CanopenNetwork
from ingenialink.canopen.register import CanopenRegister
from ingenialink.exceptions import ILRegisterNotFoundError


def monitoring_example(args: argparse.Namespace) -> List[NDArray[np.float_]]:
    registers_key = [
        "DRV_PROT_TEMP_VALUE",
    ]

    can_device = CAN_DEVICE(args.transceiver)
    can_baudrate = CAN_BAUDRATE(args.baudrate)
    net = CanopenNetwork(device=can_device, channel=args.channel, baudrate=can_baudrate)
    servo = net.connect_to_slave(target=args.node_id, dictionary=args.dictionary_path)
    # Monitoring
    # Remove all mapped registers
    try:
        servo.monitoring_disable()
    except ILRegisterNotFoundError:
        print("Monitoring is not available for this drive")
        net.disconnect_from_slave(servo)
        return []

    servo.monitoring_remove_all_mapped_registers()

    # Calculate the monitoring frequency
    ccp_value = 12
    servo.write("MON_DIST_FREQ_DIV", ccp_value, subnode=0)
    position_velocity_loop_rate = servo.read("DRV_POS_VEL_RATE")
    if not isinstance(position_velocity_loop_rate, (float, int)):
        raise TypeError(
            "Read register expected numeric value, but received string or byte",
            position_velocity_loop_rate,
        )
    sampling_freq = round(position_velocity_loop_rate / ccp_value, 2)
    read_process_finished = False
    tmp_mon_data: List[NDArray[np.float_]] = []
    monitor_data: List[NDArray[np.float_]] = []

    for idx, key in enumerate(registers_key):
        reg = servo.dictionary.registers(1)[key]
        if not isinstance(reg, CanopenRegister):
            raise TypeError("Expected register type to be CanopenRegister.")
        mapped_reg = reg.idx
        dtype_value = servo.dictionary.registers(1)[key].dtype.value
        servo.monitoring_set_mapped_register(idx, mapped_reg, 1, dtype_value, 4)
        tmp_mon_data.append(np.ndarray([]))
        monitor_data.append(np.ndarray([]))
    # Configure monitoring SOC as forced
    servo.write("MON_CFG_SOC_TYPE", 0, subnode=0)
    # Configure monitoring EoC as number of samples
    servo.write("MON_CFG_EOC_TYPE", 3, subnode=0)
    # Configure number of samples
    window_samples = 599
    total_num_samples = window_samples
    servo.write("MON_CFG_WINDOW_SAMP", window_samples, subnode=0)
    # Enable monitoring
    servo.monitoring_enable()
    # Check monitoring status
    monitor_status = servo.read("MON_DIST_STATUS", subnode=0)
    if not isinstance(monitor_status, int):
        raise TypeError("Expected monitor status to be of type int.")
    if (monitor_status & 0x1) != 1:
        raise ValueError(f"ERROR MONITOR STATUS: {monitor_status}")
    # Force Trigger
    servo.write("MON_CMD_FORCE_TRIGGER", 1, subnode=0)
    sampling_time_s = 1 / sampling_freq
    data_obtained = False

    # Start reading
    while not read_process_finished:
        try:
            monit_nmb_blocks = servo.read("MON_CFG_CYCLES_VALUE", subnode=0)
            if not isinstance(monit_nmb_blocks, (float, int)):
                raise TypeError(
                    "Read register expected numeric value, but received string or byte",
                    position_velocity_loop_rate,
                )
            if monit_nmb_blocks > 0:
                servo.monitoring_read_data()
                for idx, key in enumerate(registers_key):
                    index = idx
                    tmp_monitor_data = servo.monitoring_channel_data(index)
                    tmp_mon_data[index] = tmp_mon_data[index] + tmp_monitor_data
                    if len(tmp_mon_data[index]) >= total_num_samples:
                        tmp_mon_data[index] = np.resize(tmp_mon_data[index], total_num_samples)
                        data_x = np.arange((window_samples) * sampling_time_s, sampling_time_s)

                        if data_x.size > len(tmp_mon_data[index]):
                            data_x = np.resize(data_x, len(tmp_mon_data[index]))
                        data_y = tmp_mon_data[index]
                        monitor_data[index] = np.round(data_y, decimals=2)
                        data_obtained = True
                if data_obtained:
                    # Single-shot mode
                    read_process_finished = True
        except Exception as e:
            print("Exception monitoring: {}".format(e))
            break
    print("Finished")

    net.disconnect_from_slave(servo)
    return monitor_data


def setup_command() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Canopen example")
    parser.add_argument("-d", "--dictionary_path", help="Path to drive dictionary", required=True)
    parser.add_argument("-n", "--node_id", default=32, type=int, help="Node ID")
    parser.add_argument(
        "-t",
        "--transceiver",
        default="ixxat",
        choices=["pcan", "kvaser", "ixxat"],
        help="CAN transceiver",
    )
    parser.add_argument(
        "-b",
        "--baudrate",
        default=1000000,
        type=int,
        choices=[50000, 100000, 125000, 250000, 500000, 1000000],
        help="CAN baudrate",
    )
    parser.add_argument("-c", "--channel", default=0, type=int, help="CAN transceiver channel")
    return parser.parse_args()


if __name__ == "__main__":
    args = setup_command()
    monitoring_example(args)
