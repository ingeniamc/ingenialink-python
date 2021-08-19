import sys

from ingenialink.ethernet.network import EthernetNetwork, NET_TRANS_PROT


def connection_example():
    net = EthernetNetwork()
    servo = net.connect_to_slave("192.168.2.22",
                                 "../../resources/dictionaries/eve-net-c_eth_1.8.1.xdf",
                                 1061,
                                 NET_TRANS_PROT.UDP)

    # Monitoring
    # Remove all mapped registers
    servo.monitoring_disable()
    servo.monitoring_remove_all_mapped_registers()

    # Calculate the monitoring frequency
    ccp_value = 10
    servo.write('MON_DIST_FREQ_DIV', ccp_value, subnode=0)
    position_velocity_loop_rate = servo.raw_read(
        'DRV_POS_VEL_RATE'
    )
    sampling_freq = round(
        position_velocity_loop_rate / ccp_value, 2
    )

    net.disconnect_from_slave(servo)


if __name__ == '__main__':
    connection_example()
    sys.exit(0)
