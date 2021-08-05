import xml.etree.ElementTree as ET
from .registers import Register, REG_ACCESS, REG_DTYPE, REG_PHY
from ..utils._utils import *
from .._ingenialink import lib


class Categories(object):
    """ Contains all categories from a CANopen Dictionary.

    Args:
        dict_ (str): Path to the Ingenia dictionary.
    """
    def __init__(self, dict_):
        self._dict = dict_
        self._cat_ids = []
        self._categories = {}   # { cat_id : label }

        self.load_cat_ids()

    def load_cat_ids(self):
        """Load category IDs from dictionary."""
        with open(self._dict, 'r') as xml_file:
            tree = ET.parse(xml_file)
        root = tree.getroot()

        for element in root.findall('./Body/Device/Categories/Category'):
            self._cat_ids.append(element.attrib['id'])
            self._categories[element.attrib['id']] = {
                'en_US': element.getchildren()[0].getchildren()[0].text
            }

    @property
    def cat_ids(self):
        """ list: Category IDs. """
        return self._cat_ids

    def labels(self, cat_id):
        """ Obtain labels for a certain category ID.

        Returns:
            dict: Labels dictionary.
        """
        return self._categories[cat_id]


class Errors(object):
    """ Categories.

    Args:
        dict_ (str): Path to the Ingenia dictionary.
    """

    def __init__(self, dict_):
        self._dict = dict_
        self._errors = {}   # { cat_id : label }

        self.load_errors()

    def load_errors(self):
        """
        Load errors from dictionary.
        """
        with open(self._dict, 'r') as xml_file:
            tree = ET.parse(xml_file)
        root = tree.getroot()

        for element in root.findall('./Body/Errors/Error'):
            label = element.getchildren()[0].getchildren()[0]
            self._errors[int(element.attrib['id'], 16)] = [
                element.attrib['id'],
                element.attrib['affected_module'],
                element.attrib['error_type'].capitalize(),
                label.text
            ]

    @property
    def errors(self):
        """ dict: Errors dictionary. """
        return self._errors


class DictionaryCANOpen(object):
    """ Contains all registers and information of a CANopen dictionary.

    Args:
        dict_ (str): Path to the Ingenia dictionary.
    """
    def __init__(self, dict_):
        self.__dict = dict_
        self.__version = '1'
        self._cats = None
        self.__subnodes = 2
        self.__regs = []
        self.read_dictionary()

    def read_dictionary(self):
        """ Reads the dictionary file and initializes all its components. """
        with open(self.__dict, 'r', encoding='utf-8') as xml_file:
            tree = ET.parse(xml_file)
        root = tree.getroot()

        # Subnodes
        if root.findall('./Body/Device/Axes/'):
            self.__subnodes = len(root.findall('./Body/Device/Axes/Axis'))

        for subnode in range(0, self.__subnodes):
            self.__regs.append({})

        # Categories
        self._cats = Categories(self.__dict)

        # Errors
        self._errors = Errors(self.__dict)

        # Version
        version_node = root.find('.Header/Version')
        if version_node is not None:
            self.__version = version_node.text

        if root.findall('./Body/Device/Axes/'):
            # For each axis
            for axis in root.findall('./Body/Device/Axes/Axis/Registers'):
                for register in axis.getchildren():
                    self.read_register(register)
        else:
            for register in root.findall('./Body/Device/Registers/Register'):
                self.read_register(register)

        # Closing xml file
        xml_file.close()

    def read_register(self, register):
        """ Reads a register from the dictionary and creates a Register instance.

        Args:
            register (str): Register instance from the dictionary. 
        """
        try:
            # Identifier
            identifier = register.attrib['id']

            # Units
            units = register.attrib['units']

            # Cyclic
            if 'cyclic' in register.attrib:
                cyclic = register.attrib['cyclic']
            else:
                cyclic = "CONFIG"

            idx = register.attrib['address'][:6]
            subidx = "0x" + register.attrib['address'][-2:]

            # Data type
            dtype = register.attrib['dtype']
            if dtype == "float":
                dtype = REG_DTYPE.FLOAT
            elif dtype == "s8":
                dtype = REG_DTYPE.S8
            elif dtype == "u8":
                dtype = REG_DTYPE.U8
            elif dtype == "u16":
                dtype = REG_DTYPE.U16
            elif dtype == "s16":
                dtype = REG_DTYPE.S16
            elif dtype == "s32":
                dtype = REG_DTYPE.S32
            elif dtype == "u32":
                dtype = REG_DTYPE.U32
            elif dtype == "str":
                dtype = REG_DTYPE.STR
            else:
                raise_err(lib.IL_EINVAL, 'Invalid data type')

            # Access
            access = register.attrib['access']
            if access == "r":
                access = REG_ACCESS.RO
            elif access == "w":
                access = REG_ACCESS.WO
            elif access == "rw":
                access = REG_ACCESS.RW
            else:
                raise_err(lib.IL_EACCESS, 'Invalid access type')

            # Subnode
            if 'subnode' in register.attrib:
                subnode = register.attrib['subnode']
            else:
                subnode = 1

            # Storage
            if 'storage' in register.attrib:
                storage = register.attrib['storage']
            else:
                storage = None

            if 'cat_id' in register.attrib:
                cat_id = register.attrib['cat_id']
            else:
                cat_id = None

            if 'internal_use' in register.attrib:
                internal_use = register.attrib['internal_use']
            else:
                internal_use = 0

            # Children
            labels_elem = None
            range_elem = None
            enums_elem = None
            for child in register.getchildren():
                if child.tag == 'Labels':
                    labels_elem = child
                elif child.tag == 'Range':
                    range_elem = child
                elif child.tag == 'Enumerations':
                    enums_elem = child

            # Labels
            labels = {}
            if labels_elem is not None:
                for label in labels_elem.getchildren():
                    labels[label.attrib['lang']] = label.text

            # Range
            reg_range = (None, None)
            if range_elem is not None:
                range_min = range_elem.attrib['min']
                range_max = range_elem.attrib['max']
                reg_range = (range_min, range_max)

            # Enumerations
            enums = []
            if enums_elem is not None:
                for enum in enums_elem.getchildren():
                    enums.append({enum.attrib['value']: enum.text})

            reg = Register(identifier, units, cyclic, idx, subidx, dtype,
                           access, subnode=subnode,
                           storage=storage, range=reg_range,
                           labels=labels, enums=enums,
                           enums_count=len(enums), cat_id=cat_id,
                           internal_use=internal_use)
            self.__regs[int(subnode)][identifier] = reg
        except Exception as e:
            # print("FAIL reading a register "+ identifier)
            pass

    def get_regs(self, subnode):
        """ Gets the register dictionary to the targeted subnode.
        
        Args:
            subnode (int): Identifier for the subnode.
        
        Returns:
            dict: Dictionary of all the registers for a subnode.
        """
        return self.__regs[subnode]

    @property
    def dict(self):
        """ dict: Returns the path of the loaded dictionary. """
        return self.__dict

    @property
    def version(self):
        """ int: Returns the version of the dictionary """
        return self.__version

    @property
    def regs(self):
        """ dict: Returns the dictionary containing all registers instances. """
        return self.__regs

    @property
    def subnodes(self):
        """ int: Returns the total amount of subnodes. """
        return self.__subnodes

    @regs.setter
    def regs(self, value):
        self.__regs = value

    @property
    def cats(self):
        """ dict: Returns the dictionary containing all categories of the dictionary. """
        return self._cats

    @cats.setter
    def cats(self, value):
        self._cats = value

    @property
    def errors(self):
        """ dict: Returns a dictionary with all the errors. """
        return self._errors

    @errors.setter
    def errors(self, value):
        self._errors = value
