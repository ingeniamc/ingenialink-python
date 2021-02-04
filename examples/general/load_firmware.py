import ifaddr
import argparse
import ingenialink as il

parser = argparse.ArgumentParser(description='Load a Driver Firmware from a file via EtherCat')
parser.add_argument('file_path', nargs="?",
                    help='path to Firmware to load')
parser.add_argument('ethernet_index', nargs="?", type=int,
                    help='index of ethernet adapter listed in --list-adapters')
parser.add_argument('-l', '--list-adapters', action='store_true', dest="list_adapters",
                    help="list of adapters in format '{index}: {name}'.")
parser.add_argument('-s, --slave', type=int, dest="slave", default=1,
                    help="number of slave (default: 1)")

group = parser.add_mutually_exclusive_group()
group.add_argument('--is-everest', action="store_const", dest="is_everest",
                   const=True, help="driver is an Everest")
group.add_argument('--no-is-everest', action="store_const", dest="is_everest",
                   const=False, help="driver is not an Everest")


def get_adapters_list():
    list_str = []
    for num, item in enumerate(ifaddr.get_adapters()):
        list_str.append("{}: {}".format(num, item.nice_name))
    return list_str


def get_adapter_by_id(index):
    return "\\Device\\NPF_{}".format(ifaddr.get_adapters()[index].name.decode("utf-8"))


def main():
    args = parser.parse_args()
    if args.list_adapters:
        print("List of adapters:")
        print("\n".join(get_adapters_list()))
        return
    if not args.file_path or not args.ethernet_index:
        print("Error: file_path and ethernet_index arguments are mandatory")
        return
    if args.is_everest is None:
        print("Error: Mandatory define if it is an Everest: --is-everest or --no-is-everest")
        return
    ethernet = get_adapter_by_id(args.ethernet_index)
    net, r = il.net.update_firmware(ethernet, args.file_path, args.is_everest, slave=args.slave)
    if r < 0:
        print("Error: Firmware update fails.")


if __name__ == '__main__':
    main()
