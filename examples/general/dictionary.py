import sys
import time
import json

import ingenialink as il

def run_example():
    net, servo = il.lucky(il.NET_PROT.MCB, "summit.xml")
    new_dict = servo.dict.regs
    # servo.registers_enums = dict()
    items = new_dict.items()
    for i in range(0, 2000):
        try:
            for key, register in items:
                # if register.enums_count > 0:
                # servo.registers_enums[register.identifier] = {}
                print(register.enums_count, register.enums)
                # for i in range(0, register.enums_count):
                #     enum = register.enums[i]
                #     servo.registers_enums[register.identifier][int(enum['value'])] = str(enum['label'])
                #     print(str(enum['label']))
            # print(json.dumps(servo.registers_enums, sort_keys=True, indent=4))
        except Exception as e:
            print("error bro", e)
            break
    print("Bye")


if __name__ == '__main__':
    test = run_example()

    sys.exit()