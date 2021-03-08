import argparse
import ingenialink as il

parser = argparse.ArgumentParser(description='Export driver configuration to a file via EtherCat')
parser.add_argument('dictionary_path', help='path to driver dictionary')
parser.add_argument('config_path', help='path to save the output')
parser.add_argument('-ip', default="192.168.2.22", help='driver ip address')

group = parser.add_mutually_exclusive_group()
group.add_argument('--udp', action="store_const", dest="protocol",
                   const=2, help="use UDP")
group.add_argument('--tcp', action="store_const", dest="protocol",
                   const=1, help="use TCP (deprecated)")


def save_config():
    args = parser.parse_args()
    protocol = args.protocol or 2  # UDP by default
    servo = None
    # Connection
    try:
        _, servo = il.lucky(il.NET_PROT.ETH, args.dictionary_path,
                            address_ip=args.ip, port_ip=1061,
                            protocol=protocol)
    except Exception as e:
        print("Error trying to connect to the servo.", str(e))
    if not servo:
        return
    servo.dict_storage_read()
    new_dict = servo.dict
    new_dict.save(args.config_path)
    print("{} created".format(args.config_path))


if __name__ == '__main__':
    save_config()
