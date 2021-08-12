import ingenialink as il
import numpy as np
import matplotlib.pyplot as plt


T_S = 1e-3
"""int: Sampling period (s)."""
MAX_SAMPLES = 200
"""int: Maximum number of samples."""
MONITOR_TIMEOUT = 5
"""int: Monitor timeout (s)."""

VEL_TGT_VAL = 40.
"""float: Target velocity (rps)."""

VEL_ACT = il.Register(address=0x00606C,
                      dtype=il.REG_DTYPE.S32,
                      access=il.REG_ACCESS.RW,
                      phy=il.REG_PHY.VEL)
"""Register: Velocity Actual."""


def main():
    # setup network and connect to the first available device
    net, servo = il.lucky(il.NET_PROT.EUSB)

    servo.units_vel = il.SERVO_UNITS_VEL.RPS

    # configure monitor (trigger: 90% of the target velocity)
    monitor = il.Monitor(servo)

    monitor.configure(t_s=T_S, max_samples=MAX_SAMPLES)
    monitor.ch_configure(0, VEL_ACT)
    monitor.trigger_configure(il.MONITOR_TRIGGER.POS, source=VEL_ACT,
                              th_pos=VEL_TGT_VAL * 0.9)

    # enable servo in PV mode
    servo.disable()
    servo.mode = il.SERVO_MODE.PV
    servo.enable()

    # start monitor, set target velocity
    monitor.start()
    servo.velocity = VEL_TGT_VAL

    # wait until acquisition finishes
    monitor.wait(MONITOR_TIMEOUT)
    t, d = monitor.data

    servo.disable()

    # plot the obtained data
    plt.rc('font', family='serif')
    plt.stem(t, d[0])
    plt.title('Actual Velocity')
    plt.xlabel('Time (ms)')
    plt.ylabel('Velocity (rps)')

    d_min = np.min(d[0])
    d_max = np.max(d[0])
    offset = 0.05
    plt.ylim([d_min * (1 - offset), d_max * (1 + offset)])

    plt.show()


if __name__ == '__main__':
    main()
