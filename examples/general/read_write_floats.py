import sys

import ingenialink as il
from ingenialink import _utils

def run_example():
    print("Run Example")
    GENERATOR_GAIN_REG = il.Register(identifier=str('GENERATOR_GAIN'), address=0x0382,
                                     dtype=il.REG_DTYPE.FLOAT,
                                     access=il.REG_ACCESS.RW)
    print("Generator gain identifier" + GENERATOR_GAIN_REG.identifier)

    net, servo = il.lucky(il.NET_PROT.MCB)

    servo.raw_write(GENERATOR_GAIN_REG, 1.666)
    print(servo.raw_read(GENERATOR_GAIN_REG))
    servo.raw_write(GENERATOR_GAIN_REG, 0.123)
    print(servo.raw_read(GENERATOR_GAIN_REG))
    servo.raw_write(GENERATOR_GAIN_REG, -0.123)
    print(servo.raw_read(GENERATOR_GAIN_REG))

if __name__ == '__main__':
    run_example()

    sys.exit()