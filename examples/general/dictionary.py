import sys

import ingenialink as il

def run_example():
    print("Run Example")

    dct = il.Dictionary('xcore.xml')

    reg = dct.regs['CONTROL_WORD']
    print(reg)

    print('Labels:')
    for lang, label in reg.labels.items():
        print(lang, label)

    net, servo = il.lucky(il.NET_PROT.MCB, dict_f='xcore.xml')
    try:
        servo.dict_storage_read()
    except:
        print("ERROR")

    new_dict = servo.dict
    new_dict.save("new_xcore_dict.xml")


if __name__ == '__main__':
    run_example()

    sys.exit()