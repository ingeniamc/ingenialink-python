import sys

from ingenialink.ethercat.network import EthercatNetwork


def connection_example():
    net = EthercatNetwork("\\Device\\NPF_{13C5D891-C81E-46CE-8651-FADBE3C9415D}")

    slaves = net.scan_slaves()
    print(slaves)

    if len(slaves) > 0:
        servo = net.connect_to_slave(
            target=slaves[0],
            dictionary='../../resources/dictionaries/cap-net-e_eoe_0.7.1.xdf')

        print(servo.read('DRV_ID_SOFTWARE_VERSION'))

        net.disconnect_from_slave(servo)


if __name__ == '__main__':
    connection_example()
    sys.exit(0)
