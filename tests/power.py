import ingenialink as il
from ingenialink import regs

emergencies = []

def on_emcy(code):
    emergencies.append(code)


class TestError(Exception):
    pass

# _EMCY = {0x542f: ("Input stage problem detected. Voltage not stable or not "
                  # "available (system protection)")}

_EMCY = {0x5430: ("S'ha detectat un problema a l'etapa d'entrada. El voltatge "
                  "no és estable o insuficient (protecció del sistema)")}

def power_supply_test(servo, timeout=6000):
    """ Detect if power supply is off.

        Args:
            servo (Servo): Servo instance.
            timeout (int, optional): Switch on timeout (ms).

        Raises:
            AssertionError: If the Vbus voltage is less than the minimum Vbus.
    """

    step = 500
    elapsed = 0
    while elapsed < timeout:
        try:
            servo.switch_on(step)
        except (il.exceptions.IngeniaLinkTimeoutError,
                il.exceptions.IngeniaLinkStateError):
            pass

        if emergencies:
            emergency = emergencies.pop()
            raise TestError(_EMCY[emergency])

        elapsed += step

    vbus = servo.read(regs.DC_VOLTAGE)
    vbus_min = servo.read(regs.HWC_V_MIN)

    assert(vbus >= vbus_min)


if __name__ == '__main__':
    net = il.Network('/dev/ttyACM0')
    servo = il.Servo(net, net.servos()[0])
    servo.emcy_subscribe(on_emcy)

    servo.fault_reset()

    power_supply_test(servo)

