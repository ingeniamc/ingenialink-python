import xml.etree.ElementTree as ET
from .registers import Register, REG_ACCESS, REG_DTYPE, REG_PHY

class Categories(object):
    """Categories.

    Args:
        dict_ (il_dict_t *): Ingenia dictionary instance.
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
        """list: Category IDs."""
        return self._cat_ids

    def labels(self, cat_id):
        """Obtain labels for a certain category ID."""

        return self._categories[cat_id]

class Errors(object):
    """Categories.

        Args:
            dict_ (il_dict_t *): Ingenia dictionary instance.
        """

    def __init__(self, dict_):
        self._dict = dict_
        self._errors = {}   # { cat_id : label }

        self.load_errors()

    def load_errors(self):
        with open(self._dict, 'r') as xml_file:
            tree = ET.parse(xml_file)
        root = tree.getroot()

        for element in root.findall('./Body/Errors/Error'):
            label = element.getchildren()[0].getchildren()[0]
            self._errors[element.attrib['id']] = [
                element.attrib['id'],
                element.attrib['affected_module'],
                element.attrib['error_type'].capitalize(),
                label.text
            ]

    @property
    def errors(self):
        return self._errors

class DictionaryCANOpen(object):
    def __init__(self, dict):
        self.__dict = dict
        self.__regs = {}
        self._cats = None
        self.read_dictionary()

    def read_dictionary(self):
        with open(self.__dict, 'r') as xml_file:
            tree = ET.parse(xml_file)
        root = tree.getroot()
        # Categories
        self._cats = Categories(self.__dict)

        # Errors
        self._errors = Errors(self.__dict)

        # Registers
        for element in root.findall('./Body/Device/Registers/Register'):
            try:
                # Identifier
                identifier = element.attrib['id']

                # Units
                units = element.attrib['units']

                # Cyclic
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

                # Subnode
                if 'subnode' in element.attrib:
                    subnode = element.attrib['subnode']
                else:
                    subnode = 1

                # Storage
                if 'storage' in element.attrib:
                    storage = element.attrib['storage']
                else:
                    storage = None

                if 'cat_id' in element.attrib:
                    cat_id = element.attrib['cat_id']
                else:
                    cat_id = None

                if 'internal_use' in element.attrib:
                    internal_use = element.attrib['internal_use']
                else:
                    internal_use = 0

                # Children
                labels_elem = None
                range_elem = None
                enums_elem = None
                for child in element.getchildren():
                    if child.tag == 'Labels':
                        labels_elem = child
                    elif child.tag == 'Range':
                        range_elem = child
                    elif child.tag == 'Enumerations':
                        enums_elem = child

                # Labels
                labels = {}
                if labels_elem:
                    for label in labels_elem.getchildren():
                        labels[label.attrib['lang']] = label.text

                # Range
                range = (None, None)
                if range_elem:
                    range_min = range_elem.attrib['min']
                    range_max = range_elem.attrib['max']
                    range = (range_min, range_max)

                # Enumerations
                enums = []
                if enums_elem:
                    for enum in enums_elem.getchildren():
                        enums.append({enum.attrib['value']: enum.text})

                # (self, identifier, units, cyclic, idx, subidx, dtype, access, phy=REG_PHY.NONE, subnode=1, storage=None,
                #                  range=None, labels={}, enums=[], enums_count=0, cat_id=None, scat_id=None, internal_use=0)

                reg = Register(identifier, units, cyclic, idx, subidx, dtype, access, subnode=subnode, storage=storage,
                               range=range, labels=labels, enums=enums, enums_count=len(enums), cat_id=cat_id,
                               internal_use=internal_use)
                self.__regs[identifier] = reg
            except:
                # print("FAIL reading a register "+ identifier)
                pass

        # Closing xml file
        xml_file.close()

    @property
    def dict(self):
        return self.__dict

    @property
    def regs(self):
        return self.__regs

    @regs.setter
    def regs(self, value):
        self.__regs = value

    @property
    def cats(self):
        return self._cats

    @cats.setter
    def cats(self, value):
        self._cats = value

    @property
    def errors(self):
        return self._errors

    @errors.setter
    def errors(self, value):
        self._errors = value
