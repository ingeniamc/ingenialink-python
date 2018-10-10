import sys
import time
import json

import ingenialink as il

def run_example():
    net, servo = il.lucky(il.NET_PROT.MCB, "summit.xml")
    new_dict = servo.dict.regs
    items = new_dict.items()
    for i in range(0, 2000):
        try:
            for key, register in items:
                print(register.enums_count, register.enums)
            print(json.dumps(servo.errors, indent=4))
        except Exception as e:
            print("Exception: ", e)
            break
    print("Bye")


if __name__ == '__main__':
    test = run_example()

    sys.exit()