from abc import ABC, abstractmethod
import xml.etree.ElementTree as ET
from ingenialink.register import REG_DTYPE, REG_ACCESS
from ingenialink import exceptions as exc


class DictionaryCategories:
    """Contains all categories from a Dictionary.

    Args:
        dict_ (str): Path to the Ingenia dictionary.

    """

    def __init__(self, dict_):
        self._dict = dict_
        self._cat_ids = []
        self._categories = {}  # { cat_id : label }

        self.load_cat_ids()

    def load_cat_ids(self):
        """Load category IDs from dictionary."""
        with open(self._dict, 'r', encoding='utf-8') as xml_file:
            tree = ET.parse(xml_file)
        root = tree.getroot()

        for element in root.findall('./Body/Device/Categories/Category'):
            self._cat_ids.append(element.attrib['id'])
            self._categories[element.attrib['id']] = {
                'en_US': element.find('./Labels/Label').text
            }

    @property
    def category_ids(self):
        """list: Category IDs."""
        return self._cat_ids

    def labels(self, cat_id):
        """Obtain labels for a certain category ID.

        Returns:
            dict: Labels dictionary.

        """
        return self._categories[cat_id]


class DictionaryErrors:
    """Errors for the dictionary.

    Args:
        dict_ (str): Path to the Ingenia dictionary.

    """

    def __init__(self, dict_):
        self._dict = dict_
        self._errors = {}  # { cat_id : label }

        self.load_errors()

    def load_errors(self):
        """Load errors from dictionary."""
        with open(self._dict, 'r', encoding='utf-8') as xml_file:
            tree = ET.parse(xml_file)
        root = tree.getroot()

        for element in root.findall('./Body/Errors/Error'):
            label = element.find('./Labels/Label')
            self._errors[int(element.attrib['id'], 16)] = [
                element.attrib['id'],
                element.attrib['affected_module'],
                element.attrib['error_type'].capitalize(),
                label.text
            ]

    @property
    def errors(self):
        """dict: Errors dictionary."""
        return self._errors


class Dictionary(ABC):
    """Ingenia dictionary Abstract Base Class.

    Args:
        dictionary_path (str): Dictionary file path.

    Raises:
        ILCreationError: If the dictionary could not be created.

    """
    def __init__(self, dictionary_path):
        self.path = dictionary_path
        """str: Path of the dictionary."""
        self.version = None
        """str: Version of the dictionary."""
        self.firmware_version = None
        """str: Firmware version declared in the dictionary."""
        self.product_code = None
        """int: Product code declared in the dictionary."""
        self.part_number = None
        """str: Part number declared in the dictionary."""
        self.revision_number = None
        """int: Revision number declared in the dictionary."""
        self.interface = None
        """str: Interface declared in the dictionary."""
        self.subnodes = None
        """int: Number of subnodes in the dictionary."""
        self.categories = None
        """Categories: Instance of all the categories in the dictionary."""
        self.errors = None
        """Errors: Instance of all the errors in the dictionary."""
        self._registers = []
        """Registers: Instance of all the registers in the dictionary"""

    def registers(self, subnode):
        """Gets the register dictionary to the targeted subnode.

        Args:
            subnode (int): Identifier for the subnode.

        Returns:
            dict: Dictionary of all the registers for a subnode.

        """
        return self._registers[subnode]

    def read_dictionary(self):
        """Reads the dictionary file and initializes all its components."""
        try:
            with open(self.path, 'r', encoding='utf-8') as xml_file:
                tree = ET.parse(xml_file)
        except FileNotFoundError:
            raise FileNotFoundError(f"There is not any xml file in the path: {self.path}")
        root = tree.getroot()

        device = root.find('./Body/Device')

        # Subnodes
        if root.findall('./Body/Device/Axes/'):
            self.subnodes = len(root.findall('./Body/Device/Axes/Axis'))

        for _ in range(self.subnodes):
            self._registers.append({})

        # Categories
        self.categories = DictionaryCategories(self.path)

        # Errors
        self.errors = DictionaryErrors(self.path)

        # Version
        version_node = root.find('.Header/Version')
        if version_node is not None:
            self.version = version_node.text

        self.firmware_version = device.attrib.get('firmwareVersion')
        product_code = device.attrib.get('ProductCode')
        if product_code is not None and product_code.isdecimal():
            self.product_code = int(product_code)
        self.part_number = device.attrib.get('PartNumber')
        revision_number = device.attrib.get('RevisionNumber')
        if revision_number is not None and revision_number.isdecimal():
            self.revision_number = int(revision_number)
        self.interface = device.attrib.get('Interface')

        if root.findall('./Body/Device/Axes/'):
            # For each axis
            for axis in root.findall('./Body/Device/Axes/Axis'):
                for register in axis.findall('./Registers/Register'):
                    self.read_register(register)
        else:
            for register in root.findall('./Body/Device/Registers/Register'):
                self.read_register(register)

        # Closing xml file
        xml_file.close()

    def __invalid_dtype(self, dtype):
        raise exc.ILValueError('Invalid data type')

    def read_register(self, register):
        """Reads a register from the dictionary and creates a Register instance.

        Args:
            register (Element): Register instance from the dictionary.

        """

        # Identifier
        identifier = register.attrib['id']

        # Units
        units = register.attrib['units']

        # Cyclic
        cyclic = register.attrib['cyclic'] if 'cyclic' in register.attrib else "CONFIG"

        # Data type
        dtype_aux = register.attrib['dtype']
        dtype_options = {
            "float": REG_DTYPE.FLOAT,
            "s8": REG_DTYPE.S8,
            "u8": REG_DTYPE.U8,
            "s16": REG_DTYPE.S16,
            "u16": REG_DTYPE.U16,
            "s32": REG_DTYPE.S32,
            "u32": REG_DTYPE.U32,
            "str": REG_DTYPE.STR
        }
        if dtype_aux in dtype_options:
            dtype = dtype_options[dtype_aux]
        else:
            raise exc.ILValueError(f"The data type {dtype_aux} does not exist the register: {identifier}")

        # Access type
        access_aux = register.attrib['access']
        access_options = {
            "r": REG_ACCESS.RO,
            "w": REG_ACCESS.WO,
            "rw": REG_ACCESS.RW
        }
        if access_aux in access_options:
            access = access_options[access_aux]
        else:
            raise exc.ILAccessError(f"The access type {access_aux} does not exist the register: {identifier}")

        # Subnode
        subnode = int(
            register.attrib['subnode']) if 'subnode' in register.attrib else 1

        # Storage
        storage = register.attrib[
            'storage'] if 'storage' in register.attrib else None

        # Category Id
        cat_id = register.attrib['cat_id'] if 'cat_id' in register.attrib else None

        # Description
        if 'desc' in register.attrib:
            internal_use = register.attrib['desc']
        else:
            internal_use = 0

        # Labels
        labels_elem = register.findall('./Labels/Label')
        labels = {label.attrib['lang']: label.text for label in labels_elem}

        # Range
        range_elem = register.find('./Range')
        reg_range = (None, None)
        if range_elem is not None:
            range_min = range_elem.attrib['min']
            range_max = range_elem.attrib['max']
            reg_range = (range_min, range_max)

        # Enumerations
        enums_elem = register.findall('./Enumerations/Enum')
        enums = [{enum.attrib['value']: enum.text} for enum in enums_elem]

        return identifier, units, cyclic, dtype, access, subnode, \
            storage, reg_range, labels, enums, cat_id, internal_use
