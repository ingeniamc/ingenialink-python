import argparse
import ingenialink as il

parser = argparse.ArgumentParser(description='Import a configuration to the driver via EtherCat')
parser.add_argument('dictionary_path', help='path to driver dictionary')
parser.add_argument('config_path', help='path to configuration to load in driver')
parser.add_argument('-ip', default="192.168.2.22", help='driver ip address')

group = parser.add_mutually_exclusive_group()
group.add_argument('--udp', action="store_const", dest="protocol",
                   const=2, help="use UDP")
group.add_argument('--tcp', action="store_const", dest="protocol",
                   const=1, help="use TCP (deprecated)")


def load_config():
    args = parser.parse_args()
    # Connection
    protocol = args.protocol or 2  # UDP by default
    servo = None
    try:
        _, servo = il.lucky(il.NET_PROT.ETH, args.dictionary_path,
                            address_ip=args.ip, port_ip=1061,
                            protocol=protocol)
    except Exception as e:
        print("Error trying to connect to the servo.", str(e))
    if not servo:
        return
    # Load and save it to the drive
    servo.dict_load(args.config_path)
    servo.dict_storage_write()
    print("{} loaded".format(args.config_path))


if __name__ == '__main__':
    load_config()
