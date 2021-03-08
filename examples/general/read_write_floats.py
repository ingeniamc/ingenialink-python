import sys
import ingenialink as il

GENERATOR_GAIN_REG = il.Register(identifier=str('GENERATOR_GAIN'),
                                 address=0x0382,
                                 dtype=il.REG_DTYPE.FLOAT,
                                 access=il.REG_ACCESS.RW,
                                 units="",
                                 cyclic="")


def run_example():
    print("Generator gain identifier: ", GENERATOR_GAIN_REG.identifier)

    net, servo = il.lucky(il.NET_PROT.ETH,
                          "resources/eve-net_1.7.1.xdf",
                          address_ip='192.168.2.22',
                          port_ip=1061,
                          protocol=2)

    servo.raw_write(GENERATOR_GAIN_REG, 1.666)
    print(servo.raw_read(GENERATOR_GAIN_REG))
    servo.raw_write(GENERATOR_GAIN_REG, 0.123)
    print(servo.raw_read(GENERATOR_GAIN_REG))
    servo.raw_write(GENERATOR_GAIN_REG, -0.123)
    print(servo.raw_read(GENERATOR_GAIN_REG))


if __name__ == '__main__':
    run_example()

    sys.exit()