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

if __name__ == '__main__':
    run_example()

    sys.exit()