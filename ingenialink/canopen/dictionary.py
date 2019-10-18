import xml.etree.ElementTree as ET
from .registers import Register, REG_ACCESS, REG_DTYPE, REG_PHY

class DictionaryCANOpen(object):
    def __init__(self, dict):
        self.__dict = dict
        self.__regs = {}
        self.read_dictionary()

    def read_dictionary(self):
        with open(self.__dict, 'r') as xml_file:
            tree = ET.parse(xml_file)
        root = tree.getroot()
        for element in root.findall('./Body/Device/Registers/Register'):
            try:
                identifier = element.attrib['id']
                units = element.attrib['units']
                if 'cyclic' in element.attrib:
                    cyclic = element.attrib['cyclic']
                else:
                    cyclic = "CONFIG"
                idx = element.attrib['address'][:6]
                subidx = "0x" + element.attrib['address'][-2:]

                # Data type
                dtype = element.attrib['dtype']
                if dtype == "u32":
                    dtype = REG_DTYPE.U32
                elif dtype == "float":
                    dtype = REG_DTYPE.FLOAT
                elif dtype == "u16":
                    dtype = REG_DTYPE.U16
                elif dtype == "s32":
                    dtype = REG_DTYPE.S32
                elif dtype == "s16":
                    dtype = REG_DTYPE.S16
                elif dtype == "str":
                    dtype = REG_DTYPE.STR
                else:
                    raise Exception

                # Access
                access = element.attrib['access']
                if access == "r":
                    access = REG_ACCESS.RO
                elif access == "w":
                    access = REG_ACCESS.WO
                elif access == "rw":
                    access = REG_ACCESS.RW
                else:
                    raise Exception

                reg = Register(identifier, units, cyclic, idx, subidx, dtype, access)
                self.__regs[identifier] = reg
            except:
                print("FAIL reading a register")


    @property
    def regs(self):
        return self.__regs

    @regs.setter
    def regs(self, value):
        self.__regs = value

