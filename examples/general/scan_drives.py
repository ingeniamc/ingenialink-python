import sys

import ingenialink as il


def run_example_scan():
    protocol = il.NET_PROT.MCB
    ports_to_scan = il.devices(protocol)
    for port in ports_to_scan:
        print(port)
        try:
            network = il.Network(protocol, port)
            servos = network.servos()
            print(servos)
            for servo in servos:
                drive = il.Servo(network, servo)
                drive.dict_load("xcore-enums-1.xml")
                value = drive.raw_read("BRAKE_POST_DELAY")
                print("Brake post delay: ", value)
        except:
            print("Network disconnected")

    try:
        input("Press ENTER")
    except SyntaxError:
        pass
    print("Stopping...")

    print("Bye")


if __name__ == '__main__':
    test = run_example_scan()

    sys.exit()