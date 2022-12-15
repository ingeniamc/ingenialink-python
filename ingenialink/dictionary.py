import xml.etree.ElementTree as ET
import ingenialogger

from abc import ABC, abstractmethod
from ingenialink.constants import SINGLE_AXIS_MINIMUM_SUBNODES
from ingenialink.register import REG_DTYPE, REG_ACCESS, REG_ADDRESS_TYPE
from ingenialink import exceptions as exc

logger = ingenialogger.get_logger(__name__)

# Dictionary constants guide:
# Each constant has this structure: DICT_ORIGIN_END
# ORIGIN: The start point of the path
# END: The end point of the path
# ORIGIN: LABELS
DICT_LABELS = "./Labels"
DICT_LABELS_LABEL = f"{DICT_LABELS}/Label"


class DictionaryCategories:
    """Contains all categories from a Dictionary.

    Args:
        list_xdf_categories (list): List of Elements from xdf file

    """

    def __init__(self, list_xdf_categories):
        self._list_xdf_categories = list_xdf_categories
        self._cat_ids = []
        self._categories = {}

        self.load_cat_ids()

    def load_cat_ids(self):
        """Load category IDs from dictionary."""
        for element in self._list_xdf_categories:
            self._cat_ids.append(element.attrib["id"])
            self._categories[element.attrib["id"]] = {"en_US": element.find(DICT_LABELS_LABEL).text}

    @property
    def category_ids(self):
        """list: Category IDs."""
        return self._cat_ids

    def labels(self, cat_id):
        """Obtain labels for a certain category ID.

        Args:
        cat_id (str):  Category ID

        Returns:
            dict: Labels dictionary.

        """
        return self._categories[cat_id]


class DictionaryErrors:
    """Errors for the dictionary.

    Args:
        list_xdf_errors (list):  List of Elements from xdf file
    """

    def __init__(self, list_xdf_errors):
        self._list_xdf_errors = list_xdf_errors
        self._errors = {}

        self.load_errors()

    def load_errors(self):
        """Load errors from dictionary."""
        for element in self._list_xdf_errors:
            label = element.find(DICT_LABELS_LABEL)
            self._errors[int(element.attrib["id"], 16)] = [
                element.attrib["id"],
                element.attrib["affected_module"],
                element.attrib["error_type"].capitalize(),
                label.text,
            ]

    @property
    def errors(self):
        """Get the errors dictionary.

        Returns:
            dict: Errors dictionary.
        """
        return self._errors


class Dictionary(ABC):
    """Ingenia dictionary Abstract Base Class.

    Args:
        dictionary_path (str): Dictionary file path.

    Raises:
        ILCreationError: If the dictionary could not be created.

    """

    # Dictionary constants guide:
    # Each constant has this structure: DICT_ORIGIN_END
    # ORIGIN: The start point of the path
    # END: The end point of the path
    # ORIGIN: ROOT
    DICT_ROOT = "."
    DICT_ROOT_HEADER = f"{DICT_ROOT}/Header"
    DICT_ROOT_VERSION = f"{DICT_ROOT_HEADER}/Version"
    DICT_ROOT_BODY = f"{DICT_ROOT}/Body"
    DICT_ROOT_DEVICE = f"{DICT_ROOT_BODY}/Device"
    DICT_ROOT_CATEGORIES = f"{DICT_ROOT_DEVICE}/Categories"
    DICT_ROOT_CATEGORY = f"{DICT_ROOT_CATEGORIES}/Category"
    DICT_ROOT_ERRORS = f"{DICT_ROOT_BODY}/Errors"
    DICT_ROOT_ERROR = f"{DICT_ROOT_ERRORS}/Error"
    DICT_ROOT_AXES = f"{DICT_ROOT_DEVICE}/Axes"
    DICT_ROOT_AXIS = f"{DICT_ROOT_AXES}/Axis"
    DICT_ROOT_REGISTERS = f"{DICT_ROOT_DEVICE}/Registers"
    DICT_ROOT_REGISTER = f"{DICT_ROOT_REGISTERS}/Register"
    # ORIGIN: REGISTERS
    DICT_REGISTERS = "./Registers"
    DICT_REGISTERS_REGISTER = f"{DICT_REGISTERS}/Register"
    # ORIGIN: RANGE
    DICT_RANGE = "./Range"
    # ORIGIN: ENUMERATIONS
    DICT_ENUMERATIONS = "./Enumerations"
    DICT_ENUMERATIONS_ENUMERATION = f"{DICT_ENUMERATIONS}/Enum"

    class AttrRegDict:
        IDENTIFIER = "identifier"
        UNITS = "units"
        CYCLIC = "cyclic"
        DTYPE = "dtype"
        ACCESS = "access"
        SUBNODE = "subnode"
        STORAGE = "storage"
        REG_RANGE = "reg_range"
        LABELS = "labels"
        ENUMS = "enums"
        CAT_ID = "cat_id"
        INT_USE = "internal_use"
        ADDRESS_TYPE = "address_type"

    dtype_xdf_options = {
        "float": REG_DTYPE.FLOAT,
        "s8": REG_DTYPE.S8,
        "u8": REG_DTYPE.U8,
        "s16": REG_DTYPE.S16,
        "u16": REG_DTYPE.U16,
        "s32": REG_DTYPE.S32,
        "u32": REG_DTYPE.U32,
        "s64": REG_DTYPE.S64,
        "u64": REG_DTYPE.U64,
        "str": REG_DTYPE.STR,
    }

    access_xdf_options = {"r": REG_ACCESS.RO, "w": REG_ACCESS.WO, "rw": REG_ACCESS.RW}

    address_type_xdf_options = {
        "NVM": REG_ADDRESS_TYPE.NVM,
        "NVM_NONE": REG_ADDRESS_TYPE.NVM_NONE,
        "NVM_CFG": REG_ADDRESS_TYPE.NVM_CFG,
        "NVM_LOCK": REG_ADDRESS_TYPE.NVM_LOCK,
        "NVM_HW": REG_ADDRESS_TYPE.NVM_HW,
    }

    def __init__(self, dictionary_path):
        self.path = dictionary_path
        """str: Path of the dictionary."""
        self.version = "1"
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
        self.subnodes = SINGLE_AXIS_MINIMUM_SUBNODES
        """int: Number of subnodes in the dictionary."""
        self.categories = None
        """DictionaryCategories: Instance of all the categories in the dictionary."""
        self.errors = None
        """DictionaryErrors: Instance of all the errors in the dictionary."""
        self._registers = []
        """list(dict): Instance of all the registers in the dictionary"""

        self.read_dictionary()

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
            with open(self.path, "r", encoding="utf-8") as xdf_file:
                tree = ET.parse(xdf_file)
        except FileNotFoundError:
            raise FileNotFoundError(f"There is not any xdf file in the path: {self.path}")
        root = tree.getroot()

        device = root.find(self.DICT_ROOT_DEVICE)

        # Subnodes
        if root.findall(self.DICT_ROOT_AXES):
            self.subnodes = len(root.findall(self.DICT_ROOT_AXIS))

        for _ in range(self.subnodes):
            self._registers.append({})

        # Categories
        list_xdf_categories = root.findall(self.DICT_ROOT_CATEGORY)
        self.categories = DictionaryCategories(list_xdf_categories)

        # Errors
        list_xdf_errors = root.findall(self.DICT_ROOT_ERROR)
        self.errors = DictionaryErrors(list_xdf_errors)

        # Version
        version_node = root.find(self.DICT_ROOT_VERSION)
        if version_node is not None:
            self.version = version_node.text

        self.firmware_version = device.attrib.get("firmwareVersion")
        product_code = device.attrib.get("ProductCode")
        if product_code is not None and product_code.isdecimal():
            self.product_code = int(product_code)
        self.part_number = device.attrib.get("PartNumber")
        revision_number = device.attrib.get("RevisionNumber")
        if revision_number is not None and revision_number.isdecimal():
            self.revision_number = int(revision_number)
        self.interface = device.attrib.get("Interface")

        if root.findall(self.DICT_ROOT_AXES):
            # For each axis
            for axis in root.findall(self.DICT_ROOT_AXIS):
                for register in axis.findall(self.DICT_REGISTERS_REGISTER):
                    current_read_register = self._read_xdf_register(register)
                    if current_read_register:
                        self._add_register_list(current_read_register)
        else:
            for register in root.findall(self.DICT_ROOT_REGISTER):
                current_read_register = self._read_xdf_register(register)
                if current_read_register:
                    self._add_register_list(current_read_register)

        # Closing xdf file
        xdf_file.close()

    def _read_xdf_register(self, register):
        """Reads a register from the dictionary and creates a Register instance.

        Args:
            register (Element): Register instance from the dictionary.

        Returns:
            dict: The current register which it has been reading
            None: When at least a mandatory attribute is not in a xdf file

        Raises:
            KeyError: If the register doesn't have an identifier.
            ValueError: If the register data type is invalid.
            ValueError: If the register access type is invalid.
            ValueError: If the register address type is invalid.
            KeyError: If some attribute is missing.

        """
        try:
            # Dictionary where the current register attributes will be saved
            current_read_register = dict()

            # Identifier
            current_read_register[self.AttrRegDict.IDENTIFIER] = register.attrib["id"]

        except KeyError as ke:
            logger.error(f"The register doesn't have an identifier. Error caught: {ke}")
            return None

        try:
            # Units
            current_read_register[self.AttrRegDict.UNITS] = register.attrib["units"]

            # Cyclic
            current_read_register[self.AttrRegDict.CYCLIC] = register.attrib.get("cyclic", "CONFIG")

            # Data type
            dtype_aux = register.attrib["dtype"]

            if dtype_aux in self.dtype_xdf_options:
                current_read_register[self.AttrRegDict.DTYPE] = self.dtype_xdf_options[dtype_aux]
            else:
                raise ValueError(
                    f"The data type {dtype_aux} does not exist for the register: "
                    f'{current_read_register["identifier"]}'
                )

            # Access type
            access_aux = register.attrib["access"]

            if access_aux in self.access_xdf_options:
                current_read_register[self.AttrRegDict.ACCESS] = self.access_xdf_options[access_aux]
            else:
                raise ValueError(
                    f"The access type {access_aux} does not exist for the register: "
                    f"{current_read_register[self.AttrRegDict.IDENTIFIER]}"
                )

            # Address type
            address_type_aux = register.attrib["address_type"]

            if address_type_aux in self.address_type_xdf_options:
                current_read_register[
                    self.AttrRegDict.ADDRESS_TYPE
                ] = self.address_type_xdf_options[address_type_aux]
            else:
                raise ValueError(
                    f"The address type {address_type_aux} does not exist for the register: "
                    f"{current_read_register[self.AttrRegDict.IDENTIFIER]}"
                )

            # Subnode
            current_read_register[self.AttrRegDict.SUBNODE] = int(register.attrib.get("subnode", 1))

            # Storage
            current_read_register[self.AttrRegDict.STORAGE] = register.attrib.get("storage")

            # Category Id
            current_read_register[self.AttrRegDict.CAT_ID] = register.attrib.get("cat_id")

            # Description
            current_read_register[self.AttrRegDict.INT_USE] = register.attrib.get("internal_use", 0)

            # Labels
            labels_elem = register.findall(DICT_LABELS_LABEL)
            current_read_register[self.AttrRegDict.LABELS] = {
                label.attrib["lang"]: label.text for label in labels_elem
            }

            # Range
            range_elem = register.find(self.DICT_RANGE)
            current_read_register[self.AttrRegDict.REG_RANGE] = (None, None)
            if range_elem is not None:
                range_min = range_elem.attrib["min"]
                range_max = range_elem.attrib["max"]
                current_read_register[self.AttrRegDict.REG_RANGE] = (
                    range_min,
                    range_max,
                )

            # Enumerations
            enums_elem = register.findall(self.DICT_ENUMERATIONS_ENUMERATION)
            current_read_register[self.AttrRegDict.ENUMS] = {
                enum.attrib["value"]: enum.text for enum in enums_elem
            }

            return current_read_register

        except KeyError as ke:
            logger.error(
                f"Register with ID {current_read_register[self.AttrRegDict.IDENTIFIER]} has not attribute {ke}"
            )
            return None

    @abstractmethod
    def _add_register_list(self, register):
        """Adds the current read register into the _registers list

        Args:
            register (dict): the current read register it will be instanced

        """
        pass
