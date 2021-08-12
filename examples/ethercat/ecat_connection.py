import sys

from ingenialink.ethercat.network import EthercatNetwork


def connection_example():
    net = EthercatNetwork("\\Device\\NPF_{192D1D2F-C684-467D-A637-EC07BD434A63}")

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
