import argparse
import math
from typing import List, Union, cast

from ingenialink.canopen.network import CAN_BAUDRATE, CAN_DEVICE, CanopenNetwork
from ingenialink.exceptions import ILRegisterNotFoundError
from ingenialink.register import REG_DTYPE


def disturbance_example(args: argparse.Namespace) -> None:
    # Frequency divider to set disturbance frequency
    divider = 100
    # Calculate time between disturbance samples
    sample_period = divider / 20000
    # The disturbance signal will be a simple harmonic motion (SHM) with frequency 0.5Hz and 2000 counts of amplitude
    signal_frequency = 0.5
    signal_amplitude = 1
    # Calculate number of samples to load a complete oscillation
    n_samples = int(1 / (signal_frequency * sample_period))
    # Generate a SHM with the formula x(t)=A*sin(t*w) where:
    # A = signal_amplitude (Amplitude)
    # t = sample_period*i (time)
    # w = signal_frequency*2*math.pi (angular frequency)
    data_pos = cast(
        List[Union[int, float]],
        [
            int(
                1000
                * signal_amplitude
                * math.sin(sample_period * i * signal_frequency * 2 * math.pi)
            )
            for i in range(n_samples)
        ],
    )
    data_vel = [
        signal_amplitude * math.sin(sample_period * i * signal_frequency * 2 * math.pi)
        for i in range(n_samples)
    ]
    data_curr_q = [
        signal_amplitude
        * math.sin(sample_period * i * signal_frequency * 2 * math.pi - math.pi / 2)
        for i in range(n_samples)
    ]
    data_curr_d = [
        signal_amplitude
        * math.sin(sample_period * i * signal_frequency * 2 * math.pi + math.pi / 2)
        for i in range(n_samples)
    ]
    data_positioning_opt = cast(
        List[Union[int, float]],
        [
            int(
                abs(
                    500
                    * signal_amplitude
                    * math.sin(sample_period * i * signal_frequency * 2 * math.pi + math.pi)
                )
            )
            for i in range(n_samples)
        ],
    )

    can_device = CAN_DEVICE(args.transceiver)
    can_baudrate = CAN_BAUDRATE(args.baudrate)
    net = CanopenNetwork(device=can_device, channel=args.channel, baudrate=can_baudrate)
    servo = net.connect_to_slave(target=args.node_id, dictionary=args.dictionary_path)

    try:
        servo.disturbance_disable()
    except ILRegisterNotFoundError:
        print("Disturbance is not available for this drive")
    else:
        servo.disturbance_remove_all_mapped_registers()
        servo.disturbance_set_mapped_register(0, 0x2021, 1, REG_DTYPE.FLOAT.value, 4)
        servo.disturbance_set_mapped_register(1, 0x2020, 1, REG_DTYPE.S32.value, 4)
        servo.disturbance_set_mapped_register(2, 0x201A, 1, REG_DTYPE.FLOAT.value, 4)
        servo.disturbance_set_mapped_register(3, 0x201B, 1, REG_DTYPE.FLOAT.value, 4)
        servo.disturbance_set_mapped_register(4, 0x2024, 1, REG_DTYPE.U16.value, 2)

        servo.disturbance_write_data(
            [0, 1, 2, 3, 4],
            [REG_DTYPE.FLOAT, REG_DTYPE.S32, REG_DTYPE.FLOAT, REG_DTYPE.FLOAT, REG_DTYPE.U16],
            [data_vel, data_pos, data_curr_q, data_curr_d, data_positioning_opt],
        )
        servo.disturbance_enable()
        servo.disturbance_disable()
    finally:
        net.disconnect_from_slave(servo)


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
    disturbance_example(args)
