import sys

from ingenialink.ethernet.eth_net import EthernetNetwork, NET_TRANS_PROT


def eth_store_parameters():
    net = EthernetNetwork()
    servo = net.connect_to_slave("192.168.2.22",
                                 "eve-net-c_eth_1.8.1.xdf",
                                 1061,
                                 NET_TRANS_PROT.UDP)

    print(servo.read('DRV_ID_SOFTWARE_VERSION'))

    try:
        servo.store_parameters(subnode=1)
        print('Store successful')
    except Exception as e:
        print('Error storing', e)

    net.disconnect_from_slave(servo)


def eth_restore_parameters():
    net = EthernetNetwork()
    servo = net.connect_to_slave("192.168.2.22",
                                 "eve-net-c_eth_1.8.1.xdf",
                                 1061,
                                 NET_TRANS_PROT.UDP)

    print(servo.read('DRV_ID_SOFTWARE_VERSION'))

    try:
        servo.restore_parameters()
        print('Restore successful')
    except Exception as e:
        print('Error restoring', e)

    net.disconnect_from_slave(servo)


if __name__ == '__main__':
    eth_store_parameters()
    eth_restore_parameters()
    sys.exit(0)
