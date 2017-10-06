from time import sleep
import ingenialink as il

def on_emcy(code):
    print('Emergency occurred: 0x{:04x}'.format(code))

def main():
    net = il.Network('/dev/ttyACM0')
    servos = net.servos()
    servo = il.Servo(net, servos[0])
    servo.emcy_subscribe(on_emcy)
    servo.emcy_subscribe(on_emcy)

    servo.fault_reset()
    servo.disable()
    assert(servo.state == il.STATE_DISABLED)
    servo.mode = il.MODE_OLS
    servo.switch_on()
    assert(servo.state == il.STATE_ON)
    servo.enable()
    assert(servo.state == il.STATE_ENABLED)

    while True:
        got = input('Enter open loop V/F: ')
        try:
            v, f = [float(p) for p in got.split()]
        except ValueError:
            break

        servo.ol_voltage = v
        servo.ol_frequency = f

    servo.disable()

if __name__ == '__main__':
    main()
