import platform

from ingenialink.ethercat.network import EthercatNetwork


def main():
    # To find the network interface ID
    # On Windows, run the command: wmic nic get name, guid
    # On linux, run the command: ip link show
    interface_id = ""
    if platform.system() == "Windows":
        interface_name = "\\Device\\NPF_" + interface_id
    else:
        interface_name = interface_id
    dictionary_path = "cap-net-e_eoe_2.5.0.xdf"
    ethercat_slave_id = 1
    net = EthercatNetwork(interface_name)
    servo = net.connect_to_slave(ethercat_slave_id, dictionary_path)
    firmware_version = servo.read('DRV_ID_SOFTWARE_VERSION')
    print(firmware_version)
    net.disconnect_from_slave(servo)


if __name__ == '__main__':
    main()
