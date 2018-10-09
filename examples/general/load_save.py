import sys
import random

import ingenialink as il

def test_read_write():
    net, servo = il.lucky(il.NET_PROT.MCB, "xcore-enums.xml")
    print("TESTING U32 REGISTER:")
    print("=====================")
    for i in range(0, 6):

        servo.dict_load("xcore-enums-1.xml")
        servo.dict_storage_write()

        print("Print brake post delay register")
        value = servo.raw_read("BRAKE_POST_DELAY")
        print("READED: "+str(value))

        rand_integer = random.randint(0, 65)
        servo.raw_write("BRAKE_POST_DELAY", rand_integer, True)
        print(str(rand_integer)+" WRITTEN")

        try:
            servo.dict_storage_read()
            dict = servo.dict
            dict.save("xcore-enums-1.xml")
        except:
            print("ERROR saving new dict")

        print("==============================")

    print("TESTING FLOAT REGISTER:")
    print("=====================")
    for i in range(0, 6):

        servo.write('DICT._ACCESS_PASSWORD', 0x65766173)
        servo.dict_load("xcore-enums-1.xml")
        servo.dict_storage_write()

        print("Print brake post delay register")
        value = round(servo.raw_read("ANGLE_OFFSET"), 6)
        print("READED: " + str(value))

        rand_float = round(random.uniform(0.0, 1.0), 6)
        servo.raw_write("ANGLE_OFFSET", rand_float, True)
        print(str(rand_float) + " WRITTEN")

        try:
            servo.dict_storage_read()
            dict = servo.dict
            dict.save("xcore-enums-1.xml")
        except:
            print("ERROR saving new dict")

        print("==============================")

    try:
        input("Press ENTER")
    except SyntaxError:
        pass
    print("Stopping...")


if __name__ == '__main__':
    test_read_write()
    sys.exit()
