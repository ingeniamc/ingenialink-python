from typing import List, Dict, Optional, Union, Tuple
from abc import ABC, abstractmethod

import xml.etree.ElementTree as ET
from pathlib import Path

import ingenialogger

from ingenialink.constants import SINGLE_AXIS_MINIMUM_SUBNODES
from ingenialink.register import Register, REG_DTYPE, REG_ACCESS, REG_ADDRESS_TYPE
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
        list_xdf_categories: List of Elements from xdf file

    """

    def __init__(self, list_xdf_categories: List[ET.Element]) -> None:
        self._list_xdf_categories = list_xdf_categories
        self._cat_ids: List[str] = []
        self._categories: Dict[str, Dict[str, str]] = {}

        self.load_cat_ids()

    def load_cat_ids(self) -> None:
        """Load category IDs from dictionary."""
        for element in self._list_xdf_categories:
            self._cat_ids.append(element.attrib["id"])
            cat_element = element.find(DICT_LABELS_LABEL)
            if cat_element is None:
                logger.warning(
                    f"The element of the category {element.attrib['id']} could not be load"
                )
                continue
            cat_id = cat_element.text
            if cat_id is None:
                logger.warning(f"The ID of the category {element.attrib['id']} could not be load")
                continue
            self._categories[element.attrib["id"]] = {"en_US": cat_id}

    @property
    def category_ids(self) -> List[str]:
        """Category IDs."""
        return self._cat_ids

    def labels(self, cat_id: str) -> Dict[str, str]:
        """Obtain labels for a certain category ID.

        Args:
        cat_id:  Category ID

        Returns:
            Labels dictionary.

        """
        return self._categories[cat_id]


class DictionaryErrors:
    """Errors for the dictionary.

    Args:
        list_xdf_errors:  List of Elements from xdf file
    """

    def __init__(self, list_xdf_errors: List[ET.Element]) -> None:
        self._list_xdf_errors = list_xdf_errors
        self._errors: Dict[int, List[Optional[str]]] = {}

        self.load_errors()

    def load_errors(self) -> None:
        """Load errors from dictionary."""
        for element in self._list_xdf_errors:
            label = element.find(DICT_LABELS_LABEL)
            if label is None:
                logger.warning(f"Could not load label of error {element.attrib['id']}")
                continue
            self._errors[int(element.attrib["id"], 16)] = [
                element.attrib["id"],
                element.attrib["affected_module"],
                element.attrib["error_type"].capitalize(),
                label.text,
            ]

    @property
    def errors(self) -> Dict[int, List[Optional[str]]]:
        """Get the errors dictionary.

        Returns:
            Errors dictionary.
        """
        return self._errors


class Dictionary(ABC):
    """Ingenia dictionary Abstract Base Class.

    Args:
        dictionary_path: Dictionary file path.

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
    DICT_IMAGE = "DriveImage"
    DICT_MOCO_IMAGE_ATTRIB = "moco"

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

    def __init__(self, dictionary_path: str) -> None:
        self.path = dictionary_path
        """Path of the dictionary."""
        self.version = "1"
        """Version of the dictionary."""
        self.firmware_version: Optional[str] = None
        """Firmware version declared in the dictionary."""
        self.product_code: Optional[int] = None
        """Product code declared in the dictionary."""
        self.part_number: Optional[str] = None
        """Part number declared in the dictionary."""
        self.revision_number: Optional[int] = None
        """Revision number declared in the dictionary."""
        self.interface: Optional[str] = None
        """Interface declared in the dictionary."""
        self.subnodes: int = SINGLE_AXIS_MINIMUM_SUBNODES
        """Number of subnodes in the dictionary."""
        self.categories: Optional[DictionaryCategories] = None
        """Instance of all the categories in the dictionary."""
        self.errors: Optional[DictionaryErrors] = None
        """Instance of all the errors in the dictionary."""
        self._registers: List[Dict[str, Register]] = []
        """Instance of all the registers in the dictionary"""
        self.image: Optional[str] = None
        """Drive's encoded image."""
        self.moco_image: Optional[str] = None
        """Motion CORE encoded image. Only available when using a COM-KIT."""

        self.read_dictionary()

    def registers(self, subnode: int) -> Dict[str, Register]:
        """Gets the register dictionary to the targeted subnode.

        Args:
            subnode: Identifier for the subnode.

        Returns:
            Dictionary of all the registers for a subnode.

        """
        return self._registers[subnode]

    def read_dictionary(self) -> None:
        """Reads the dictionary file and initializes all its components."""
        try:
            with open(self.path, "r", encoding="utf-8") as xdf_file:
                tree = ET.parse(xdf_file)
        except FileNotFoundError:
            raise FileNotFoundError(f"There is not any xdf file in the path: {self.path}")
        root = tree.getroot()

        device = root.find(self.DICT_ROOT_DEVICE)
        if device is None:
            raise exc.ILError(
                f"Could not load the dictionary {self.path}. Device information is missing"
            )

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
        if version_node is not None and version_node.text is not None:
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
        try:
            images = root.findall(self.DICT_IMAGE)
            for image in images:
                if image.text is not None and image.text.strip():
                    if (
                        "type" in image.attrib
                        and image.attrib["type"] == self.DICT_MOCO_IMAGE_ATTRIB
                    ):
                        self.moco_image = image.text
                    else:
                        self.image = image.text
        except AttributeError:
            logger.error(f"Dictionary {Path(self.path).name} has no image section.")
        # Closing xdf file
        xdf_file.close()

    def _read_xdf_register(self, register: ET.Element) -> Optional[Register]:
        """Reads a register from the dictionary and creates a Register instance.

        Args:
            register: Register instance from the dictionary.

        Returns:
            The current register which it has been reading
            None: When at least a mandatory attribute is not in a xdf file

        Raises:
            KeyError: If the register doesn't have an identifier.
            ValueError: If the register data type is invalid.
            ValueError: If the register access type is invalid.
            ValueError: If the register address type is invalid.
            KeyError: If some attribute is missing.

        """
        try:
            identifier = register.attrib["id"]
        except KeyError as ke:
            logger.error(f"The register doesn't have an identifier. Error caught: {ke}")
            return None

        try:
            units = register.attrib["units"]
            cyclic = register.attrib.get("cyclic", "CONFIG")

            # Data type
            dtype_aux = register.attrib["dtype"]
            dtype = None
            if dtype_aux in self.dtype_xdf_options:
                dtype = self.dtype_xdf_options[dtype_aux]
            else:
                raise ValueError(
                    f"The data type {dtype_aux} does not exist for the register: {identifier}"
                )

            # Access type
            access_aux = register.attrib["access"]
            access = None
            if access_aux in self.access_xdf_options:
                access = self.access_xdf_options[access_aux]
            else:
                raise ValueError(
                    f"The access type {access_aux} does not exist for the register: {identifier}"
                )

            # Address type
            address_type_aux = register.attrib["address_type"]

            if address_type_aux in self.address_type_xdf_options:
                address_type = self.address_type_xdf_options[address_type_aux]
            else:
                raise ValueError(
                    f"The address type {address_type_aux} does not exist for the register: "
                    f"{identifier}"
                )

            subnode = int(register.attrib.get("subnode", 1))
            storage = register.attrib.get("storage")
            cat_id = register.attrib.get("cat_id")
            internal_use = int(register.attrib.get("internal_use", 0))

            # Labels
            labels_elem = register.findall(DICT_LABELS_LABEL)
            labels = {label.attrib["lang"]: str(label.text) for label in labels_elem}

            # Range
            range_elem = register.find(self.DICT_RANGE)
            reg_range: Union[Tuple[None, None], Tuple[str, str]] = (None, None)
            if range_elem is not None:
                range_min = range_elem.attrib["min"]
                range_max = range_elem.attrib["max"]
                reg_range = (range_min, range_max)

            # Enumerations
            enums_elem = register.findall(self.DICT_ENUMERATIONS_ENUMERATION)
            enums = []
            for enum in enums_elem:
                dictionary: Dict[str, Union[str, int]] = {
                    "label": str(enum.text),
                    "value": int(enum.attrib["value"]),
                }
                enums.append(dictionary)

            current_read_register = Register(
                dtype,
                access,
                identifier=identifier,
                units=units,
                cyclic=cyclic,
                subnode=subnode,
                storage=storage,
                reg_range=reg_range,
                labels=labels,
                enums=enums,
                cat_id=cat_id,
                internal_use=internal_use,
                address_type=address_type,
            )

            return current_read_register

        except KeyError as ke:
            logger.error(f"Register with ID {identifier} has not attribute {ke}")
            return None

    def _add_register_list(
        self,
        register: Register,
    ) -> None:
        """Adds the current read register into the _registers list

        Args:
            register: the current read register it will be instanced

        """
        identifier = register.identifier
        subnode = register.subnode
        if identifier is None:
            return
        self._registers[subnode][identifier] = register
