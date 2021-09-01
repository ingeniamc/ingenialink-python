import ingenialink as il
import sys
import math
from ingenialink.ethercat.network import EthercatNetwork


def disturbance_example():
    # Disturbance register
    target_register = "CL_POS_SET_POINT_VALUE"
    # Frequency divider to set disturbance frequency
    divider = 20
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

    net = EthercatNetwork(
            interface_name="\\Device\\NPF_{13C5D891-C81E-46CE-8651-FADBE3C9415D}")
    servo = net.connect_to_slave(
        target=1,
        dictionary='../../resources/dictionaries/eve-xcr-e_eoe_1.8.1.xdf')

    servo.monitoring_disable()
    servo.disturbance_remove_all_mapped_registers()
    servo.disturbance_set_mapped_register(0, 0x0021, il.register.REG_DTYPE.FLOAT.value)
    servo.disturbance_set_mapped_register(1, 0x0020, il.register.REG_DTYPE.S32.value)
    servo.disturbance_set_mapped_register(2, 0x001A, il.register.REG_DTYPE.FLOAT.value)
    servo.disturbance_set_mapped_register(3, 0x001B, il.register.REG_DTYPE.FLOAT.value)
    servo.disturbance_set_mapped_register(4, 0x0024, il.register.REG_DTYPE.U16.value)

    servo.disturbance_write_data([0,1,2,3,4],
                                 [il.register.REG_DTYPE.FLOAT,
                                  il.register.REG_DTYPE.S32,
                                  il.register.REG_DTYPE.FLOAT,
                                  il.register.REG_DTYPE.FLOAT,
                                  il.register.REG_DTYPE.U16],
                                 [data_vel, data_pos, data_curr_q, data_curr_d, data_positioning_opt])
    servo.monitoring_enable()


if __name__ == '__main__':
    disturbance_example()
    sys.exit(0)