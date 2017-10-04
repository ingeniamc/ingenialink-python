import ingenialink as il
from ingenialink import regs
import numpy as np
import matplotlib.pyplot as plt

DEV = '/dev/ttyACM0'
""" str: Network device. """

T_S = 1000
""" int: Sampling period (us). """
MAX_SAMPLES = 200
""" int: Maximum number of samples. """
MONITOR_TIMEOUT = 5000
""" int: Monitor timeout (ms). """

VEL_TGT = 20.
""" float: Target velocity (rps). """


def main():
    # setup network and connect to the first available device
    net = il.Network(DEV)
    axes = net.axes()
    axis = il.Axis(net, axes[0])

    axis.units_vel = il.UNITS_VEL_RPS

    # configure monitor (trigger: 90% of the target velocity)
    monitor = il.Monitor(axis)

    monitor.configure(t_s=T_S, max_samples=MAX_SAMPLES)
    monitor.ch_disable_all()
    monitor.ch_configure(il.MONITOR_CH_1, regs.VEL_ACT)
    monitor.trigger_configure(il.MONITOR_TRIGGER_POS, source=regs.VEL_ACT,
                              th_pos=VEL_TGT * 0.9)

    # enable axis in PV mode
    axis.disable()
    axis.mode = il.MODE_PV
    axis.enable()

    # start monitor, set target velocity
    monitor.start()
    axis.velocity = VEL_TGT

    # wait until acquisition finishes
    monitor.wait(MONITOR_TIMEOUT)
    data = monitor.data

    axis.disable()

    # plot the obtained data
    d = data[il.MONITOR_CH_1]
    t = np.arange(0, len(d) * T_S / 1000., T_S / 1000.)

    plt.rc('font', family='serif')
    plt.stem(t, d)
    plt.title('Actual Velocity')
    plt.xlabel('Time (ms)')
    plt.ylabel('Velocity (rps)')

    d_min = np.min(d)
    d_max = np.max(d)
    offset = 0.05
    plt.ylim([d_min * (1 - offset), d_max * (1 + offset)])

    plt.show()


if __name__ == '__main__':
    main()
