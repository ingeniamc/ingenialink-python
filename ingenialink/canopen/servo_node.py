import canopen
import struct
import xml.etree.ElementTree as ET

from .._ingenialink import ffi, lib
from .dictionary import DictionaryCANOpen
from .registers import Register, REG_DTYPE, REG_ACCESS

class Servo(object):
    def __init__(self, net, node, dict):
        self.__net = net
        self.__node = node
        self.__dict = DictionaryCANOpen(dict)
        self.__info = {}
        self.init_info()

    def init_info(self):
        name = "Drive"
        serial_number = self.raw_read('SERIAL_NUMBER')
        product_code = self.raw_read('PRODUCT_CODE')
        sw_version = self.raw_read('SOFTWARE_VERSION')
        revision_number = self.raw_read('REVISION_NUMBER')
        hw_variant = 'A'

        self.__info = {
            'serial': serial_number,
            'name': name,
            'sw_version': sw_version,
            'hw_variant': hw_variant,
            'prod_code': product_code,
            'revision': revision_number
        }

    def raw_read(self, reg):
        """ Raw read from servo.

            Args:
                reg (Register): Register.

            Returns:
                int: Otained value

            Raises:
                TypeError: If the register type is not valid.
        """

        if isinstance(reg, Register):
            _reg = reg
        elif isinstance(reg, str):
            _dict = self.__dict
            if not _dict:
                raise ValueError('No dictionary loaded')

            _reg = _dict.regs[reg]
        else:
            raise TypeError('Invalid register')

        access = _reg.access
        if access == REG_ACCESS.WO:
            raise TypeError('Register is Write-only')

        dtype = _reg.dtype
        try:
            if dtype == REG_DTYPE.S8:
                value = int.from_bytes(self.__node.sdo.upload(int(_reg.idx, 16), int(_reg.subidx, 16)), "little",
                                       signed=True)
            elif dtype == REG_DTYPE.S16:
                value = int.from_bytes(self.__node.sdo.upload(int(_reg.idx, 16), int(_reg.subidx, 16)), "little",
                                       signed=True)
            elif dtype == REG_DTYPE.S32:
                value = int.from_bytes(self.__node.sdo.upload(int(_reg.idx, 16), int(_reg.subidx, 16)), "little",
                                       signed=True)
            elif dtype == REG_DTYPE.FLOAT:
                [value] = struct.unpack('f', self.__node.sdo.upload(int(_reg.idx, 16), int(_reg.subidx, 16)))
            elif dtype == REG_DTYPE.STR:
                value = self.__node.sdo.upload(int(_reg.idx, 16), int(_reg.subidx, 16)).decode("utf-8")
            else:
                value = int.from_bytes(self.__node.sdo.upload(int(_reg.idx, 16), int(_reg.subidx, 16)), "little")
        except Exception as e:
            print(e)
            raise("Read error")
        return value

    def read(self, reg):
        """ Read from servo.

            Args:
                reg (str, Register): Register.

            Returns:
                float: Otained value

            Raises:
                TypeError: If the register type is not valid.
        """
        return self.raw_read(reg)

    def write(self, reg, data, confirm=True, extended=0):
        return self.raw_write(reg, data, confirm=True, extended=0)

    def raw_write(self, reg, data, confirm=True, extended=0):
        """ Raw write to servo.

            Args:
                reg (Register): Register.
                data (int): Data.
                confirm (bool, optional): Confirm write.
                extended (int, optional): Extended frame.

            Raises:
                TypeError: If any of the arguments type is not valid or
                    unsupported.
        """

        if isinstance(reg, Register):
            _reg = reg
        elif isinstance(reg, str):
            _dict = self.__dict
            if not _dict:
                raise ValueError('No dictionary loaded')

            _reg = _dict.regs[reg]
        else:
            raise TypeError('Invalid register')

        if _reg.access == REG_ACCESS.RO:
            raise TypeError('Register is Read-only')

        # auto cast floats if register is not float
        if isinstance(data, float) and _reg.dtype != REG_DTYPE.FLOAT:
            data = int(data)

        try:
            if _reg.dtype == REG_DTYPE.FLOAT:
                self.__node.sdo.download(int(_reg.idx, 16), int(_reg.subidx, 16),
                                         struct.pack('f', data))
            else:
                bytes_length = 2
                signed = False
                if _reg.dtype == REG_DTYPE.U16:
                    bytes_length = 2
                elif _reg.dtype == REG_DTYPE.S16:
                    bytes_length = 2
                    signed = True
                elif _reg.dtype == REG_DTYPE.U32:
                    bytes_length = 4
                elif _reg.dtype == REG_DTYPE.S32:
                    bytes_length = 4
                    signed = True

                self.__node.sdo.download(int(_reg.idx, 16), int(_reg.subidx, 16),
                                         data.to_bytes(bytes_length, byteorder='little', signed=signed))
        except Exception as e:
            print(_reg.identifier + " : " + e)
            raise ("Write error")

    def get_all_registers(self):
        for obj in self.__node.object_dictionary.values():
            print('0x%X: %s' % (obj.index, obj.name))
            if isinstance(obj, canopen.objectdictionary.Record):
                for subobj in obj.values():
                    print('  %d: %s' % (subobj.subindex, subobj.name))

    def dict_storage_read(self, new_path):
        """Read all dictionary registers content and put it to the dictionary
        storage."""

        with open(self.__dict.dict, 'r+') as xml_file:
            tree = ET.parse(xml_file)
        root = tree.getroot()

        for element in root.findall('./Body/Device/Registers/Register'):
            try:
                if element.attrib['access'] == 'rw':
                    storage = self.raw_read(element.attrib['id'])
                    element.set('storage', str(storage))

                    # Update register object
                    reg = self.__dict.regs[element.attrib['id']]
                    reg.storage = storage
                    reg.storage_valid = 1
            except Exception as e:
                # print("Exception during dict_storage_read, register " + element.attrib['id'] + ": ", str(e))
                pass

        tree.write(new_path)
        xml_file.close()

    def dict_storage_write(self, path):
        """Write current dictionary storage to the servo drive."""
        with open(path, 'r+') as xml_file:
            tree = ET.parse(xml_file)
        root = tree.getroot()

        for element in root.findall('./Body/Device/Registers/Register'):
            try:
                if 'storage' in element.attrib and element.attrib['access'] == 'rw':
                    self.raw_write(element.attrib['id'], float(element.attrib['storage']))
            except Exception as e:
                # print("Exception during dict_storage_write, register " + element.attrib['id'] + ": ", str(e))
                pass

    def store_all(self):
        """ Store all servo current parameters to the NVM. """
        r = 0
        try:
            self.raw_write("STORE_ALL", 0x65766173)
        except:
            r = -1
        return r

    def dict_load(self, dict_f):
        """ Load dictionary.

            Args:
                dict_f (str): Dictionary.
        """
        try:
            self.__dict = DictionaryCANOpen(dict_f)
        except Exception as e:
            print("Error loading a dictionary")

    def state_subscribe(self, cb):
        """ Subscribe to state changes.

            Args:
                cb: Callback

            Returns:
                int: Assigned slot.
        """
        return 0

    @property
    def dict(self):
        """ Dictionary: Dictionary. """
        return self.__dict

    @property
    def errors(self):
        """ dict: Errors. """
        return self.__dict.errors

    @property
    def info(self):
        """ dict: Servo information. """
        return self.__info

    @property
    def state(self):
        """ tuple: Servo state and state flags. """
        return lib.IL_SERVO_STATE_NRDY
