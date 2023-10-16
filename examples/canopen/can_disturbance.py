import sys
import math

from ingenialink.canopen.network import CanopenNetwork, CAN_DEVICE, CAN_BAUDRATE
from ingenialink.register import REG_DTYPE


def disturbance_example():
    # Frequency divider to set disturbance frequency
    divider = 100
    # Calculate time between disturbance samples
    sample_period = divider/20000
    # The disturbance signal will be a simple harmonic motion (SHM) with frequency 0.5Hz and 2000 counts of amplitude
    signal_frequency = 0.5
    signal_amplitude = 1
    # Calculate number of samples to load a complete oscillation
    n_samples = int(1 / (signal_frequency * sample_period))
    # Generate a SHM with the formula x(t)=A*sin(t*w) where:
    # A = signal_amplitude (Amplitude)
    # t = sample_period*i (time)
    # w = signal_frequency*2*math.pi (angular frequency)
    data_pos = [int(1000*signal_amplitude * math.sin(sample_period*i * signal_frequency * 2*math.pi)) for i in range(n_samples)]
    data_vel = [signal_amplitude * math.sin(sample_period*i * signal_frequency * 2*math.pi) for i in range(n_samples)]
    data_curr_q = [signal_amplitude * math.sin(sample_period*i * signal_frequency * 2*math.pi - math.pi/2) for i in range(n_samples)]
    data_curr_d = [signal_amplitude * math.sin(sample_period*i * signal_frequency * 2*math.pi + math.pi/2) for i in range(n_samples)]
    data_positioning_opt = [int(abs(500*signal_amplitude * math.sin(sample_period*i * signal_frequency * 2*math.pi + math.pi))) for i in range(n_samples)]

    net = CanopenNetwork(device=CAN_DEVICE.IXXAT,
                         channel=0,
                         baudrate=CAN_BAUDRATE.Baudrate_1M)
    nodes = net.scan_slaves()
    servo = net.connect_to_slave(
        target=nodes[0],
        dictionary='../../resources/dictionaries/eve-net-c_can_1.8.1.xdf')

    servo.disturbance_disable()
    servo.disturbance_remove_all_mapped_registers()
    servo.disturbance_set_mapped_register(0, 0x2021, 1, REG_DTYPE.FLOAT.value, 4)
    servo.disturbance_set_mapped_register(1, 0x2020, 1, REG_DTYPE.S32.value, 4)
    servo.disturbance_set_mapped_register(2, 0x201A, 1, REG_DTYPE.FLOAT.value, 4)
    servo.disturbance_set_mapped_register(3, 0x201B, 1, REG_DTYPE.FLOAT.value, 4)
    servo.disturbance_set_mapped_register(4, 0x2024, 1, REG_DTYPE.U16.value, 2)

    servo.disturbance_write_data([0,1,2,3,4],
                                 [REG_DTYPE.FLOAT,
                                  REG_DTYPE.S32,
                                  REG_DTYPE.FLOAT,
                                  REG_DTYPE.FLOAT,
                                  REG_DTYPE.U16],
                                 [data_vel, data_pos, data_curr_q, data_curr_d, data_positioning_opt])
    servo.disturbance_enable()
    servo.disturbance_disable()
    net.disconnect_from_slave(servo)


if __name__ == '__main__':
    disturbance_example()
    sys.exit(0)