import copy
import enum
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple, Union

import ingenialogger

from ingenialink.bitfield import BitField
from ingenialink.canopen.register import CanopenRegister
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.ethernet.register import EthernetRegister
from ingenialink.exceptions import ILDictionaryParseError
from ingenialink.register import REG_ACCESS, REG_ADDRESS_TYPE, REG_DTYPE, RegCyclicType, Register

logger = ingenialogger.get_logger(__name__)

# Dictionary constants guide:
# Each constant has this structure: DICT_ORIGIN_END
# ORIGIN: The start point of the path
# END: The end point of the path
# ORIGIN: LABELS
DICT_LABELS = "./Labels"
DICT_LABELS_LABEL = f"{DICT_LABELS}/Label"


class Interface(enum.Enum):
    """Connection Interfaces"""

    CAN = enum.auto()
    """CANopen"""
    ETH = enum.auto()
    """Ethernet"""
    ECAT = enum.auto()
    """EtherCAT"""
    EoE = enum.auto()
    """Ethernet over EtherCAT"""
    VIRTUAL = enum.auto()
    """Virtual Drive"""


class SubnodeType(enum.Enum):
    """Subnode types"""

    COMMUNICATION = enum.auto()
    """Communication"""
    MOTION = enum.auto()
    """Motion"""
    SAFETY = enum.auto()
    """Safety"""


@dataclass
class DictionarySafetyPDO:
    """Safety PDOs dictionary descriptor"""

    @dataclass
    class PDORegister:
        """PDO register descriptor"""

        register: Optional[CanopenRegister]
        size: int

    index: int
    entries: List[PDORegister]


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


@dataclass
class DictionaryError:
    id: int
    """The error ID."""

    affected_module: str
    """The module affected by the error."""

    error_type: str
    """The error type."""

    description: Optional[str]
    """The error description."""

    def __iter__(self) -> Iterator[Union[str, None]]:
        id_hex_string = f"0x{self.id:08X}"
        return iter((id_hex_string, self.affected_module, self.error_type, self.description))


@dataclass
class DictionaryDescriptor:
    firmware_version: Optional[str] = None
    """Firmware version declared in the dictionary."""
    product_code: Optional[int] = None
    """Product code declared in the dictionary."""
    part_number: Optional[str] = None
    """Part number declared in the dictionary."""
    revision_number: Optional[int] = None
    """Revision number declared in the dictionary."""


class Dictionary(ABC):
    """Ingenia dictionary Abstract Base Class.

    Args:
        dictionary_path: Dictionary file path.
        interface: communication interface.

    Raises:
        ILDictionaryParseError: If the dictionary could not be created.

    """

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
        "bool": REG_DTYPE.BOOL,
        "byteArray512": REG_DTYPE.BYTE_ARRAY_512,
    }

    access_xdf_options = {"r": REG_ACCESS.RO, "w": REG_ACCESS.WO, "rw": REG_ACCESS.RW}

    address_type_xdf_options = {
        "NVM": REG_ADDRESS_TYPE.NVM,
        "NVM_NONE": REG_ADDRESS_TYPE.NVM_NONE,
        "NVM_CFG": REG_ADDRESS_TYPE.NVM_CFG,
        "NVM_LOCK": REG_ADDRESS_TYPE.NVM_LOCK,
        "NVM_HW": REG_ADDRESS_TYPE.NVM_HW,
    }

    subnode_xdf_options = {
        "Communication": SubnodeType.COMMUNICATION,
        "Motion": SubnodeType.MOTION,
        "Safety": SubnodeType.SAFETY,
    }

    version: str
    """Version of the dictionary."""
    firmware_version: Optional[str] = None
    """Firmware version declared in the dictionary."""
    product_code: Optional[int] = None
    """Product code declared in the dictionary."""
    coco_product_code: Optional[int] = None
    """CoCo product code declared in the dictionary.
    Only used when a COM-KIT and a CORE dictionary are merged."""
    part_number: Optional[str] = None
    """Part number declared in the dictionary."""
    revision_number: Optional[int] = None
    """Revision number declared in the dictionary."""
    interface: Interface
    """Interface declared in the dictionary."""
    subnodes: Dict[int, SubnodeType]
    """Number of subnodes in the dictionary."""
    categories: DictionaryCategories
    """Instance of all the categories in the dictionary."""
    errors: Dict[int, "DictionaryError"]
    """Instance of all the errors in the dictionary."""
    image: Optional[str] = None
    """Drive's encoded image."""
    is_safe: bool = False
    """True if has SafetyPDOs element, else False"""
    _registers: Dict[int, Dict[str, Register]]
    """Instance of all the registers in the dictionary"""
    registers_group: Dict[int, Dict[str, List[Register]]]
    """Registers group by subnode and UID"""
    safety_rpdos: Dict[str, DictionarySafetyPDO]
    """Safety RPDOs by UID"""
    safety_tpdos: Dict[str, DictionarySafetyPDO]
    """Safety TPDOs by UID"""

    def __init__(self, dictionary_path: str, interface: Interface) -> None:
        self.registers_group = {}
        self.safety_rpdos = {}
        self.safety_tpdos = {}
        self._registers = {}
        self.subnodes = {}
        self.path = dictionary_path
        """Path of the dictionary."""
        self.interface = interface
        try:
            self.read_dictionary()
        except KeyError as e:
            raise ILDictionaryParseError("The dictionary is not well-formed.") from e

    @classmethod
    @abstractmethod
    def get_description(cls, dictionary_path: str, interface: Interface) -> DictionaryDescriptor:
        """Quick function to get target dictionary description

        Args:
            dictionary_path: target dictionary path
            interface: device interface

        Returns:
            Target dictionary description
        """
        pass

    def __add__(self, other_dict: "Dictionary") -> "Dictionary":
        """Merge two dictionary instances.

        It can only be used for merging COM-KIT and CORE dictionaries.

        Returns:
            A new dictionary instance with the attributes merged.

        """
        if not isinstance(other_dict, type(self)):
            raise TypeError(
                f"Cannot merge dictionaries. Expected type: {type(self)}, got: {type(other_dict)}"
            )
        if not other_dict.is_coco_dictionary and not self.is_coco_dictionary:
            raise ValueError(
                "Cannot merge dictionaries. One of the dictionaries must be a COM-KIT dictionary."
            )
        self_dict_copy = copy.deepcopy(self)
        other_dict_copy = copy.deepcopy(other_dict)
        self_dict_copy._merge_registers(other_dict_copy)
        self_dict_copy._merge_errors(other_dict_copy)
        self_dict_copy._merge_attributes(other_dict_copy)
        self_dict_copy._set_image(other_dict_copy)
        return self_dict_copy

    def registers(self, subnode: int) -> Dict[str, Register]:
        """Gets the register dictionary to the targeted subnode.

        Args:
            subnode: Identifier for the subnode.

        Returns:
            Dictionary of all the registers for a subnode.

        """
        return self._registers[subnode]

    @abstractmethod
    def read_dictionary(self) -> None:
        """Reads the dictionary file and initializes all its components."""
        pass

    def child_registers(self, uid: str, subnode: int) -> List[Register]:
        """Return group registers by an UID

        Args:
            uid: registers group UID
            subnode: registers group subnode

        Returns:
            All registers in the group

        Raises:
            KeyError: Registers group does not exist

        """
        if subnode in self.registers_group and uid in self.registers_group[subnode]:
            return self.registers_group[subnode][uid]
        raise KeyError(f"Registers group {uid} in subnode {subnode} not exist")

    def get_safety_rpdo(self, uid: str) -> DictionarySafetyPDO:
        """Get Safe RPDO by uid

        Args:
            uid: Safe RPDO uid

        Returns:
            PDO object description

        Raises:
            NotImplementedError: Device is not safe
            KeyError: Safe RPDO not exist

        """
        if not self.is_safe:
            raise NotImplementedError("Safe PDOs are not implemented for this device")
        if uid in self.safety_rpdos:
            return self.safety_rpdos[uid]
        raise KeyError(f"Safe RPDO {uid} not exist")

    def get_safety_tpdo(self, uid: str) -> DictionarySafetyPDO:
        """Get Safe TPDO by uid

        Args:
            uid: Safe TPDO uid

        Returns:
            PDO object description

        Raises:
            NotImplementedError: Device is not safe
            KeyError: Safe TPDO not exist

        """
        if not self.is_safe:
            raise NotImplementedError("Safe PDOs are not implemented for this device")
        if uid in self.safety_tpdos:
            return self.safety_tpdos[uid]
        raise KeyError(f"Safe TPDO {uid} not exist")

    def _merge_registers(self, other_dict: "Dictionary") -> None:
        """Add the registers from another dictionary to the dictionary instance.

        Args:
            other_dict: The other dictionary instance.

        """
        for subnode, registers in other_dict._registers.items():
            self._registers[subnode].update(registers)

    def _merge_errors(self, other_dict: "Dictionary") -> None:
        """Add the errors from another dictionary to the dictionary instance.

        Args:
            other_dict: The other dictionary instance.

        """
        self.errors.update(other_dict.errors)

    def _set_image(self, other_dict: "Dictionary") -> None:
        """Set the image attribute.

        Choose the image from the dictionary that has one.

        Args:
            other_dict: The other dictionary instance.

        """
        core_dict = self if other_dict.is_coco_dictionary else other_dict
        self.image = core_dict.image

    def _merge_attributes(self, other_dict: "Dictionary") -> None:
        """Add the revision number, product code, firmware version and part number
        from the other dictionary to the dictionary instance.

        Args:
            other_dict: The other dictionary instance.

        """
        if not other_dict.is_coco_dictionary:
            self.coco_product_code = self.product_code
            self.product_code = other_dict.product_code
            self.revision_number = other_dict.revision_number
            self.firmware_version = other_dict.firmware_version
            self.part_number = other_dict.part_number
        else:
            self.coco_product_code = other_dict.product_code

    def _read_errors(self, root: ET.Element, path: str) -> None:
        """Process Errors element and set errors

        Args:
            root: Errors element

        """
        error_list = self._findall_and_check(root, path)
        self._load_errors(error_list)

    @staticmethod
    def _findall_and_check(root: ET.Element, path: str) -> List[ET.Element]:
        """Return list of elements in the target root element if exist, else, raises an exception.

        Args:
          root: root element
          path: target elements path

        Returns:
          list of path elements

        Raises:
          ILDictionaryParseError: path elements not found

        """
        element = root.findall(path)
        if not element:
            raise ILDictionaryParseError(f"{path} element is not found")
        return element

    def _load_errors(self, error_list: List[ET.Element]) -> None:
        """Parse and load the errors into the errors dictionary"""
        self.errors = {}
        for element in error_list:
            label = element.find(DICT_LABELS_LABEL)
            if label is None:
                logger.warning(f"Could not load label of error {element.attrib['id']}")
                continue
            error_id = int(element.attrib["id"], 16)
            error_description = label.text
            error_type = element.attrib["error_type"].capitalize()
            error_affected_module = element.attrib["affected_module"]
            self.errors[error_id] = DictionaryError(
                error_id, error_affected_module, error_type, error_description
            )

    @property
    def is_coco_dictionary(self) -> bool:
        """Check if dictionary is a CoCo dictionary

        Returns:
            True if the dictionary is a CoCo dictionary. False otherwise.

        """
        return len(self.registers(1)) == 0


class DictionaryV3(Dictionary):
    __DRIVE_IMAGE_ELEMENT = "DriveImage"

    __HEADER_ELEMENT = "Header"
    __VERSION_ELEMENT = "Version"

    __BODY_ELEMENT = "Body"

    __CATEGORIES_ELEMENT = "Categories"
    __CATEGORY_ELEMENT = "Category"

    __DEVICES_ELEMENT = "Devices"
    __DEVICE_ELEMENT = {
        Interface.CAN: "CANDevice",
        Interface.ETH: "ETHDevice",
        Interface.ECAT: "ECATDevice",
        Interface.EoE: "EoEDevice",
    }
    __DEVICE_FW_VERSION_ATTR = "firmwareVersion"
    __DEVICE_PRODUCT_CODE_ATTR = "ProductCode"
    __DEVICE_PART_NUMBER_ATTR = "PartNumber"
    DEVICE_REVISION_NUMBER_ATTR = "RevisionNumber"

    __SUBNODES_ELEMENT = "Subnodes"
    __SUBNODE_ELEMENT = "Subnode"
    __SUBNODE_INDEX_ATTR = "index"

    __SUBNODE_ATTR = "subnode"
    __ADDRESS_TYPE_ATTR = "address_type"
    __ACCESS_ATTR = "access"
    __DTYPE_ATTR = "dtype"
    __UID_ATTR = "id"
    __CYCLIC_ATTR = "cyclic"
    __DESCRIPTION_ATTR = "desc"
    __DEFAULT_ATTR = "default"
    __CAT_ID_ATTR = "cat_id"
    __UNITS_ATTR = "units"
    __IS_NODE_ID_DEPENDENT_ATTR = "is_node_id_dependent"
    __IS_NODE_ID_DEPENDENT_TRUE_ATTR_VALUE = "true"

    __CANOPEN_OBJECTS_ELEMENT = "CANopenObjects"
    __CANOPEN_OBJECT_ELEMENT = "CANopenObject"
    __SUBITEMS_ELEMENT = "Subitems"
    __SUBITEM_ELEMENT = "Subitem"
    __INDEX_ATTR = "index"
    __SUBINDEX_ATTR = "subindex"

    __MCB_REGISTERS_ELEMENT = "MCBRegisters"
    __MCB_REGISTER_ELEMENT = "MCBRegister"
    __ADDRESS_ATTR = "address"

    __ERRORS_ELEMENT = "Errors"
    __ERROR_ELEMENT = "Error"

    __LABELS_ELEMENT = "Labels"
    __LABEL_ELEMENT = "Label"
    __LABEL_LANG_ATTR = "lang"

    __ENUMERATIONS_ELEMENT = "Enumerations"
    __ENUM_ELEMENT = "Enum"
    __ENUM_VALUE_ATTR = "value"

    __BITFIELDS_ELEMENT = "BitFields"
    __BITFIELD_ELEMENT = "BitField"
    __BITFIELD_NAME = "name"
    __BITFIELD_START = "start"
    __BITFIELD_END = "end"

    __RANGE_ELEMENT = "Range"
    __RANGE_MIN_ATTR = "min"
    __RANGE_MAX_ATTR = "max"

    __SAFETY_PDOS_ELEMENT = "SafetyPDOs"
    __RPDO_ELEMENT = "RPDO"
    __TPDO_ELEMENT = "TPDO"
    __PDO_UID_ATTR = "id"
    __PDO_INDEX_ATTR = "index"
    __PDO_ENTRY_ELEMENT = "PDOEntry"
    __PDO_ENTRY_SIZE_ATTR = "size"
    __PDO_ENTRY_SUBNODE_ATTR = "subnode"

    @classmethod
    def get_description(cls, dictionary_path: str, interface: Interface) -> DictionaryDescriptor:
        try:
            with open(dictionary_path, "r", encoding="utf-8") as xdf_file:
                tree = ET.parse(xdf_file)
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"There is not any xdf file in the path: {dictionary_path}"
            ) from e
        root = tree.getroot()
        device_path = (
            f"{cls.__BODY_ELEMENT}/{cls.__DEVICES_ELEMENT}/{cls.__DEVICE_ELEMENT[interface]}"
        )
        device = root.find(device_path)
        if device is None:
            raise ILDictionaryParseError("Dictionary cannot be used for the chosen communication")
        firmware_version = device.attrib[cls.__DEVICE_FW_VERSION_ATTR]
        product_code = int(device.attrib[cls.__DEVICE_PRODUCT_CODE_ATTR])
        part_number = device.attrib[cls.__DEVICE_PART_NUMBER_ATTR]
        revision_number = int(device.attrib[cls.DEVICE_REVISION_NUMBER_ATTR])
        return DictionaryDescriptor(firmware_version, product_code, part_number, revision_number)

    @staticmethod
    def __find_and_check(root: ET.Element, path: str) -> ET.Element:
        """Return the path element in the target root element if exists, else, raises an exception.

        Args:
            root: root element
            path: target element path

        Returns:
            path element

        Raises:
            ILDictionaryParseError: path element not found

        """
        element = root.find(path)
        if element is None:
            raise ILDictionaryParseError(f"{path} element is not found")
        return element

    def read_dictionary(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as xdf_file:
                tree = ET.parse(xdf_file)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"There is not any xdf file in the path: {self.path}") from e
        root = tree.getroot()
        drive_image_element = self.__find_and_check(root, self.__DRIVE_IMAGE_ELEMENT)
        self.__read_drive_image(drive_image_element)
        header_element = self.__find_and_check(root, self.__HEADER_ELEMENT)
        self.__read_header(header_element)
        body_element = self.__find_and_check(root, self.__BODY_ELEMENT)
        self.__read_body(body_element)

    def __read_drive_image(self, drive_image: ET.Element) -> None:
        """Process DriveImage element and set image

        Args:
            drive_image: DriveImage element

        """
        if drive_image.text is not None and drive_image.text.strip():
            self.image = drive_image.text.strip()
        else:
            self.image = None

    def __read_header(self, root: ET.Element) -> None:
        """Process Header element

        Args:
            root: Header element

        """
        version_element = self.__find_and_check(root, self.__VERSION_ELEMENT)
        self.__read_version(version_element)
        # Dictionary localization not implemented

    def __read_version(self, root: ET.Element) -> None:
        """Process Version element and set version

        Args:
            root: Version element

        Raises:
            ILDictionaryParseError: version is empty

        """
        if root.text is None:
            raise ILDictionaryParseError("Version is empty")
        self.version = root.text.strip()

    def __read_body(self, root: ET.Element) -> None:
        """Process Body element

        Args:
            root: Body element

        """
        categories_element = self.__find_and_check(root, self.__CATEGORIES_ELEMENT)
        self.__read_categories(categories_element)
        devices_element = self.__find_and_check(root, self.__DEVICES_ELEMENT)
        self.__read_devices(devices_element)

    def __read_categories(self, root: ET.Element) -> None:
        """Process Categories element and set categories

        Args:
            root: Categories element

        """
        category_list = self._findall_and_check(root, self.__CATEGORY_ELEMENT)
        self.categories = DictionaryCategories(category_list)

    def __read_devices(self, root: ET.Element) -> None:
        """Process Devices element

        Args:
            root: Devices element

        """
        if self.interface == Interface.VIRTUAL:
            device_element = root.find(self.__DEVICE_ELEMENT[Interface.ETH])
            if device_element is None:
                device_element = root.find(self.__DEVICE_ELEMENT[Interface.EoE])
                self.interface = Interface.EoE
            else:
                self.interface = Interface.ETH
        else:
            device_element = root.find(self.__DEVICE_ELEMENT[self.interface])
        if device_element is None:
            raise ILDictionaryParseError("Dictionary cannot be used for the chosen communication")
        self.__read_device_attributes(device_element)
        if self.interface == Interface.ETH:
            self.__read_device_eth(device_element)
        if self.interface == Interface.CAN:
            self.__read_device_can(device_element)
        if self.interface == Interface.ECAT:
            self.__read_device_ecat(device_element)
        if self.interface == Interface.EoE:
            self.__read_device_eoe(device_element)

    def __read_device_attributes(self, device: ET.Element) -> None:
        self.firmware_version = device.attrib[self.__DEVICE_FW_VERSION_ATTR]
        self.product_code = int(device.attrib[self.__DEVICE_PRODUCT_CODE_ATTR])
        self.part_number = device.attrib[self.__DEVICE_PART_NUMBER_ATTR]
        self.revision_number = int(device.attrib[self.DEVICE_REVISION_NUMBER_ATTR])

    def __read_device_eoe(self, root: ET.Element) -> None:
        """Process EoEDevice element

        Args:
            root: EoEDevice element

        """
        # Device element is identical
        self.__read_device_eth(root)

    def __read_device_eth(self, root: ET.Element) -> None:
        """Process ETHDevice element

        Args:
            root: ETHDevice element

        """
        subnodes_element = self.__find_and_check(root, self.__SUBNODES_ELEMENT)
        self.__read_subnodes(subnodes_element)
        registers_element = self.__find_and_check(root, self.__MCB_REGISTERS_ELEMENT)
        register_element_list = self._findall_and_check(
            registers_element, self.__MCB_REGISTER_ELEMENT
        )
        for register_element in register_element_list:
            self.__read_mcb_register(register_element)
        errors_element = self.__find_and_check(root, self.__ERRORS_ELEMENT)
        self._read_errors(errors_element, self.__ERROR_ELEMENT)

    def __read_device_ecat(self, root: ET.Element) -> None:
        """Process ECATDevice element

        Args:
            root: ECATDevice element

        """
        subnodes_element = self.__find_and_check(root, self.__SUBNODES_ELEMENT)
        self.__read_subnodes(subnodes_element)
        registers_element = self.__find_and_check(root, self.__CANOPEN_OBJECTS_ELEMENT)
        register_element_list = self._findall_and_check(
            registers_element, self.__CANOPEN_OBJECT_ELEMENT
        )
        for register_element in register_element_list:
            self.__read_canopen_object(register_element)
        errors_element = self.__find_and_check(root, self.__ERRORS_ELEMENT)
        self._read_errors(errors_element, self.__ERROR_ELEMENT)
        safety_pdos_element = root.find(self.__SAFETY_PDOS_ELEMENT)
        if safety_pdos_element is not None:
            self.__read_safety_pdos(safety_pdos_element)

    def __read_device_can(self, root: ET.Element) -> None:
        """Process CANDevice element

        Args:
            root: CANDevice element

        """
        subnodes_element = self.__find_and_check(root, self.__SUBNODES_ELEMENT)
        self.__read_subnodes(subnodes_element)
        registers_element = self.__find_and_check(root, self.__CANOPEN_OBJECTS_ELEMENT)
        register_element_list = self._findall_and_check(
            registers_element, self.__CANOPEN_OBJECT_ELEMENT
        )
        for register_element in register_element_list:
            self.__read_canopen_object(register_element)
        errors_element = self.__find_and_check(root, self.__ERRORS_ELEMENT)
        self._read_errors(errors_element, self.__ERROR_ELEMENT)

    def __read_subnodes(self, root: ET.Element) -> None:
        """Process Subnodes element and fill subnodes

        Args:
            root: Subnodes element

        Raises:
            ILDictionaryParseError: Subnode element text is None

        """
        subnode_list = self._findall_and_check(root, self.__SUBNODE_ELEMENT)
        for subnode in subnode_list:
            if subnode.text is None:
                raise ILDictionaryParseError("Subnode element text is None")
            self.subnodes[
                int(subnode.attrib[self.__SUBNODE_INDEX_ATTR])
            ] = self.subnode_xdf_options[subnode.text.strip()]

    def __read_labels(self, root: ET.Element) -> Dict[str, str]:
        """Process Labels element

        Args:
            root: Labels element

        Returns:
            labels by localization

        """
        label_list = self._findall_and_check(root, self.__LABEL_ELEMENT)
        labels = {}
        for label in label_list:
            key, value = self.__read_label(label)
            labels[key] = value
        return labels

    def __read_label(self, label: ET.Element) -> Tuple[str, str]:
        """Process Label element

        Args:
            label: Label element

        Returns:
            Tuple with label localization and label text

        Raises:
            ILDictionaryParseError: Label text is empty

        """
        if label.text is None:
            raise ILDictionaryParseError("Label text is empty")
        return label.attrib[self.__LABEL_LANG_ATTR], label.text.strip()

    def __read_range(
        self, range_elem: Optional[ET.Element]
    ) -> Union[Tuple[None, None], Tuple[str, str]]:
        """Process Range element

        Args:
            range_elem: Range element

        Returns:
            Tuple with minimum and maximum range, None if range is not limited

        """
        if range_elem is not None:
            range_min = range_elem.attrib[self.__RANGE_MIN_ATTR]
            range_max = range_elem.attrib[self.__RANGE_MAX_ATTR]
            return range_min, range_max
        return None, None

    def __read_enumeration(
        self, enumerations_element: Optional[ET.Element]
    ) -> Optional[Dict[str, int]]:
        """Process Enumerations possible element

        Args:
            enumerations_element: Enumerations element, also accepts None

        Returns:
            If Enumerations is not None, return enums values

        """
        if enumerations_element is not None:
            enum_list = self._findall_and_check(enumerations_element, self.__ENUM_ELEMENT)
            return {
                str(enum_element.text.strip()): int(enum_element.attrib[self.__ENUM_VALUE_ATTR])
                for enum_element in enum_list
                if enum_element.text is not None
            }
        return None

    def __read_bitfields(
        self, bitfields_element: Optional[ET.Element]
    ) -> Optional[Dict[str, BitField]]:
        """Process Bitfields possible element

        Args:
            bitfields_element: Bitfields element, also accepts None

        Returns:
            If Bitfields is not None, return bitfields definitions

        """
        if bitfields_element is not None:
            bitfields_list = self._findall_and_check(bitfields_element, self.__BITFIELD_ELEMENT)
            return {
                bitfield_element.attrib[self.__BITFIELD_NAME]: BitField(
                    int(bitfield_element.attrib[self.__BITFIELD_START]),
                    int(bitfield_element.attrib[self.__BITFIELD_END]),
                )
                for bitfield_element in bitfields_list
            }

        return None

    def __read_mcb_register(self, register: ET.Element) -> None:
        """Process MCBRegister element and add it to _registers

        Args:
            register: MCBRegister element

        """
        reg_address = int(register.attrib[self.__ADDRESS_ATTR], 16)
        subnode = int(register.attrib[self.__SUBNODE_ATTR])
        address_type = self.address_type_xdf_options[register.attrib[self.__ADDRESS_TYPE_ATTR]]
        access = self.access_xdf_options[register.attrib[self.__ACCESS_ATTR]]
        dtype = self.dtype_xdf_options[register.attrib[self.__DTYPE_ATTR]]
        identifier = register.attrib[self.__UID_ATTR]
        cyclic = RegCyclicType(register.attrib[self.__CYCLIC_ATTR])
        description = register.attrib[self.__DESCRIPTION_ATTR]
        default = bytes.fromhex(register.attrib[self.__DEFAULT_ATTR])
        cat_id = register.attrib[self.__CAT_ID_ATTR]
        units = register.attrib.get(self.__UNITS_ATTR)
        # Labels
        labels_element = self.__find_and_check(register, self.__LABELS_ELEMENT)
        labels = self.__read_labels(labels_element)
        # Range
        range_elem = register.find(self.__RANGE_ELEMENT)
        reg_range = self.__read_range(range_elem)
        # Enumerations
        enumerations_element = register.find(self.__ENUMERATIONS_ELEMENT)
        enums = self.__read_enumeration(enumerations_element)
        # Bitfields
        bitfields_element = register.find(self.__BITFIELDS_ELEMENT)
        bitfields = self.__read_bitfields(bitfields_element)

        ethernet_register = EthernetRegister(
            reg_address,
            dtype,
            access,
            identifier=identifier,
            units=units,
            cyclic=cyclic,
            subnode=subnode,
            reg_range=reg_range,
            labels=labels,
            enums=enums,
            cat_id=cat_id,
            address_type=address_type,
            description=description,
            default=default,
            bitfields=bitfields,
        )
        if subnode not in self._registers:
            self._registers[subnode] = {}
        self._registers[subnode][identifier] = ethernet_register

    def __read_canopen_object(self, root: ET.Element) -> None:
        """Process CANopenObject element and add it to registers_group if has UID

        Args:
            root: CANopenObject element

        """
        object_uid = root.attrib.get(self.__UID_ATTR)
        reg_index = int(root.attrib[self.__INDEX_ATTR], 16)
        subnode = int(root.attrib[self.__SUBNODE_ATTR])
        subitmes_element = self.__find_and_check(root, self.__SUBITEMS_ELEMENT)
        subitem_list = self._findall_and_check(subitmes_element, self.__SUBITEM_ELEMENT)
        register_list = [
            self.__read_canopen_subitem(subitem, reg_index, subnode) for subitem in subitem_list
        ]
        if object_uid:
            register_list.sort(key=lambda val: val.subidx)
            if subnode not in self.registers_group:
                self.registers_group[subnode] = {}
            self.registers_group[subnode][object_uid] = list(register_list)

    def __read_canopen_subitem(
        self, subitem: ET.Element, reg_index: int, subnode: int
    ) -> CanopenRegister:
        """Process Subitem element and add it to _registers

        Args:
            subitem: CANopenObject element
            reg_index: register index
            subnode: register subnode

        Returns:
            Subitem register

        """
        reg_subindex = int(subitem.attrib[self.__SUBINDEX_ATTR])
        address_type = self.address_type_xdf_options[subitem.attrib[self.__ADDRESS_TYPE_ATTR]]
        access = self.access_xdf_options[subitem.attrib[self.__ACCESS_ATTR]]
        dtype = self.dtype_xdf_options[subitem.attrib[self.__DTYPE_ATTR]]
        identifier = subitem.attrib[self.__UID_ATTR]
        cyclic = RegCyclicType(subitem.attrib[self.__CYCLIC_ATTR])
        description = subitem.attrib[self.__DESCRIPTION_ATTR]
        default = bytes.fromhex(subitem.attrib[self.__DEFAULT_ATTR])
        cat_id = subitem.attrib[self.__CAT_ID_ATTR]
        units = subitem.attrib.get(self.__UNITS_ATTR)
        is_node_id_dependent = (
            subitem.attrib.get(self.__IS_NODE_ID_DEPENDENT_ATTR)
            == self.__IS_NODE_ID_DEPENDENT_TRUE_ATTR_VALUE
        )
        # Labels
        labels_element = self.__find_and_check(subitem, self.__LABELS_ELEMENT)
        labels = self.__read_labels(labels_element)
        # Range
        range_elem = subitem.find(self.__RANGE_ELEMENT)
        reg_range = self.__read_range(range_elem)
        # Enumerations
        enumerations_element = subitem.find(self.__ENUMERATIONS_ELEMENT)
        enums = self.__read_enumeration(enumerations_element)
        # Bitfields
        bitfields_element = subitem.find(self.__BITFIELDS_ELEMENT)
        bitfields = self.__read_bitfields(bitfields_element)

        canopen_register = CanopenRegister(
            reg_index,
            reg_subindex,
            dtype,
            access,
            identifier=identifier,
            units=units,
            cyclic=cyclic,
            subnode=subnode,
            reg_range=reg_range,
            labels=labels,
            enums=enums,
            cat_id=cat_id,
            address_type=address_type,
            description=description,
            default=default,
            bitfields=bitfields,
            is_node_id_dependent=is_node_id_dependent,
        )
        if subnode not in self._registers:
            self._registers[subnode] = {}
        self._registers[subnode][identifier] = canopen_register
        return canopen_register

    def __read_safety_pdos(self, root: ET.Element) -> None:
        """Process SafetyPDOs element

        Args:
            root: MCBRegister element

        """
        self.is_safe = True
        rpdo_list = self._findall_and_check(root, self.__RPDO_ELEMENT)
        for rpdo_element in rpdo_list:
            uid, safety_rpdo = self.__read_pdo(rpdo_element)
            self.safety_rpdos[uid] = safety_rpdo
        tpdo_list = self._findall_and_check(root, self.__TPDO_ELEMENT)
        for tpdo_element in tpdo_list:
            uid, safety_tpdo = self.__read_pdo(tpdo_element)
            self.safety_tpdos[uid] = safety_tpdo

    def __read_pdo(self, pdo: ET.Element) -> Tuple[str, DictionarySafetyPDO]:
        """Process RPDO and TPDO elements

        Args:
            pdo: MCBRegister element

        Returns:
            PDO uid and class description

        Raises:
            ILDictionaryParseError: PDO register does not exist

        """
        uid = pdo.attrib[self.__PDO_UID_ATTR]
        pdo_index = int(pdo.attrib[self.__PDO_INDEX_ATTR], 16)
        entry_list = self._findall_and_check(pdo, self.__PDO_ENTRY_ELEMENT)
        pdo_registers = []
        for entry in entry_list:
            size = int(entry.attrib[self.__PDO_ENTRY_SIZE_ATTR])
            reg_subnode = int(entry.attrib.get(self.__PDO_ENTRY_SUBNODE_ATTR, 1))
            reg_uid = entry.text
            if reg_uid:
                if not (reg_subnode in self._registers and reg_uid in self._registers[reg_subnode]):
                    raise ILDictionaryParseError(
                        f"PDO entry {reg_uid} subnode {reg_subnode} does not exist"
                    )
                entry_reg = self._registers[reg_subnode][reg_uid]
                if not isinstance(entry_reg, CanopenRegister):
                    raise ValueError(f"{reg_uid} subnode {reg_subnode} is not a CANopen register")
                pdo_registers.append(DictionarySafetyPDO.PDORegister(entry_reg, size))
            else:
                pdo_registers.append(DictionarySafetyPDO.PDORegister(None, size))
        return uid, DictionarySafetyPDO(pdo_index, pdo_registers)


class DictionaryV2(Dictionary):
    # Dictionary constants guide:
    # Each constant has this structure: DICT_ORIGIN_END
    # ORIGIN: The start point of the path
    # END: The end point of the path
    # ORIGIN: ROOT
    __DICT_ROOT = "."
    __DICT_ROOT_HEADER = f"{__DICT_ROOT}/Header"
    __DICT_ROOT_VERSION = f"{__DICT_ROOT_HEADER}/Version"
    __DICT_ROOT_BODY = f"{__DICT_ROOT}/Body"
    __DICT_ROOT_DEVICE = f"{__DICT_ROOT_BODY}/Device"
    __DICT_ROOT_CATEGORIES = f"{__DICT_ROOT_DEVICE}/Categories"
    __DICT_ROOT_CATEGORY = f"{__DICT_ROOT_CATEGORIES}/Category"
    __DICT_ROOT_ERRORS = f"{__DICT_ROOT_BODY}/Errors"
    __DICT_ROOT_ERROR = f"{__DICT_ROOT_ERRORS}/Error"
    __DICT_ROOT_AXES = f"{__DICT_ROOT_DEVICE}/Axes"
    __DICT_ROOT_AXIS = f"{__DICT_ROOT_AXES}/Axis"
    __DICT_ROOT_REGISTERS = f"{__DICT_ROOT_DEVICE}/Registers"
    __DICT_ROOT_REGISTER = f"{__DICT_ROOT_REGISTERS}/Register"
    # ORIGIN: REGISTERS
    __DICT_REGISTERS = "./Registers"
    __DICT_REGISTERS_REGISTER = f"{__DICT_REGISTERS}/Register"
    # ORIGIN: RANGE
    __DICT_RANGE = "./Range"
    # ORIGIN: ENUMERATIONS
    __DICT_ENUMERATIONS = "./Enumerations"
    __DICT_ENUMERATIONS_ENUMERATION = f"{__DICT_ENUMERATIONS}/Enum"
    __DICT_IMAGE = "DriveImage"

    dict_interface: Optional[str]

    __MON_DIST_STATUS_REGISTER = "MON_DIST_STATUS"

    _MONITORING_DISTURBANCE_REGISTERS: Union[
        List[EthercatRegister], List[EthernetRegister], List[CanopenRegister]
    ]

    _KNOWN_REGISTER_BITFIELDS: Dict[str, Callable[[], Dict[str, BitField]]] = {
        "DRV_STATE_STATUS": lambda: {
            # https://drives.novantamotion.com/summit/0x011-status-word
            "READY_TO_SWITCH_ON": BitField.bit(0),
            "SWITCHED_ON": BitField.bit(1),
            "OPERATION_ENABLED": BitField.bit(2),
            "FAULT": BitField.bit(3),
            "VOLTAGE_ENABLED": BitField.bit(4),
            "QUICK_STOP": BitField.bit(5),
            "SWITCH_ON_DISABLED": BitField.bit(6),
            "WARNING": BitField.bit(7),
            "TARGET_REACHED": BitField.bit(10),
            "SWITCH_LIMITS_ACTIVE": BitField.bit(11),
            "COMMUTATION_FEEDBACK_ALIGNED": BitField.bit(14),
        },
        "DRV_STATE_CONTROL": lambda: {
            # https://drives.novantamotion.com/summit/0x010-control-word
            "SWITCH_ON": BitField.bit(0),
            "VOLTAGE_ENABLE": BitField.bit(1),
            "QUICK_STOP": BitField.bit(2),
            "ENABLE_OPERATION": BitField.bit(3),
            "RUN_SET_POINT_MANAGER": BitField.bit(4),
            "FAULT_RESET": BitField.bit(7),
        },
        "DRV_OP_CMD": lambda: {
            # https://drives.novantamotion.com/summit/0x014-operation-mode
            "OPERATION_MODE": BitField(0, 3),
            "PROFILER_MODE": BitField(4, 6),
            "PTP_BUFFER": BitField.bit(7),
            "HOMING": BitField.bit(8),
        },
        "DRV_PROT_STO_STATUS": lambda: {
            # https://drives.novantamotion.com/summit/0x51a-sto-status
            "STO1": BitField.bit(0),
            "STO2": BitField.bit(1),
            "STO_SUPPLY_FAULT": BitField.bit(2),
            "STO_ABNORMAL_FAULT": BitField.bit(3),
            "STO_REPORT": BitField.bit(4),
        },
    }

    _INTERFACE_STR = {
        Interface.CAN: "CAN",
        Interface.ECAT: "ETH",
        Interface.EoE: "ETH",
        Interface.ETH: "ETH",
    }

    def __init__(self, dictionary_path: str) -> None:
        super().__init__(dictionary_path, self.interface)

    @classmethod
    def get_description(cls, dictionary_path: str, interface: Interface) -> DictionaryDescriptor:
        try:
            with open(dictionary_path, "r", encoding="utf-8") as xdf_file:
                tree = ET.parse(xdf_file)
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"There is not any xdf file in the path: {dictionary_path}"
            ) from e
        root = tree.getroot()
        device = root.find(cls.__DICT_ROOT_DEVICE)
        if device is None:
            raise ILDictionaryParseError(
                f"Could not load the dictionary {dictionary_path}. Device information is missing"
            )
        dict_interface = device.attrib.get("Interface")
        if cls._INTERFACE_STR[interface] != dict_interface and dict_interface is not None:
            raise ILDictionaryParseError("Dictionary cannot be used for the chosen communication")
        firmware_version = device.attrib.get("firmwareVersion")
        product_code = device.attrib.get("ProductCode")
        if product_code is not None and product_code.isdecimal():
            product_code = int(product_code)
        else:
            product_code = None
        part_number = device.attrib.get("PartNumber")
        revision_number = device.attrib.get("RevisionNumber")
        if revision_number is not None and revision_number.isdecimal():
            revision_number = int(revision_number)
        else:
            revision_number = None
        return DictionaryDescriptor(firmware_version, product_code, part_number, revision_number)

    def read_dictionary(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as xdf_file:
                tree = ET.parse(xdf_file)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"There is not any xdf file in the path: {self.path}") from e
        root = tree.getroot()

        device = root.find(self.__DICT_ROOT_DEVICE)
        if device is None:
            raise ILDictionaryParseError(
                f"Could not load the dictionary {self.path}. Device information is missing"
            )

        # Subnodes
        if root.findall(self.__DICT_ROOT_AXES):
            self.subnodes[0] = SubnodeType.COMMUNICATION
            for i in range(1, len(root.findall(self.__DICT_ROOT_AXIS))):
                self.subnodes[i] = SubnodeType.MOTION
        else:
            self.subnodes[0] = SubnodeType.COMMUNICATION
            self.subnodes[1] = SubnodeType.MOTION

        for subnode in self.subnodes:
            self._registers[subnode] = {}

        # Categories
        list_xdf_categories = root.findall(self.__DICT_ROOT_CATEGORY)
        self.categories = DictionaryCategories(list_xdf_categories)

        # Errors
        self._read_errors(root, self.__DICT_ROOT_ERROR)

        # Version
        version_node = root.find(self.__DICT_ROOT_VERSION)
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
        self.dict_interface = device.attrib.get("Interface")
        if (
            self.interface != Interface.VIRTUAL
            and self._INTERFACE_STR[self.interface] != self.dict_interface
            and self.dict_interface is not None
        ):
            raise ILDictionaryParseError("Dictionary cannot be used for the chosen communication")

        if root.findall(self.__DICT_ROOT_AXES):
            # For each axis
            for axis in root.findall(self.__DICT_ROOT_AXIS):
                for register in axis.findall(self.__DICT_REGISTERS_REGISTER):
                    current_read_register = self._read_xdf_register(register)
                    if current_read_register:
                        self._add_register_list(current_read_register)
        else:
            for register in root.findall(self.__DICT_ROOT_REGISTER):
                current_read_register = self._read_xdf_register(register)
                if current_read_register:
                    self._add_register_list(current_read_register)
        try:
            image = root.find(self.__DICT_IMAGE)
            if image is not None and image.text is not None and image.text.strip():
                self.image = image.text
        except AttributeError:
            logger.error(f"Dictionary {Path(self.path).name} has no image section.")
        # Closing xdf file
        xdf_file.close()
        self._append_missing_registers()

    def _read_xdf_register(self, register: ET.Element) -> Optional[Register]:
        """Reads a register from the dictionary and creates a Register instance.

        Args:
            register: Register instance from the dictionary.

        Returns:
            The current register which it has been reading
            None: When at least a mandatory attribute is not in a xdf file

        Raises:
            ILDictionaryParseError: If the register data type is invalid.
            ILDictionaryParseError: If the register access type is invalid.
            ILDictionaryParseError: If the register address type is invalid.
            KeyError: If some attribute is missing.

        """
        try:
            identifier = register.attrib["id"]
        except KeyError as ke:
            logger.error(f"The register doesn't have an identifier. Error caught: {ke}")
            return None

        try:
            units = register.attrib["units"]
            cyclic = RegCyclicType(register.attrib.get("cyclic", "CONFIG"))

            # Data type
            dtype_aux = register.attrib["dtype"]
            dtype = None
            if dtype_aux in self.dtype_xdf_options:
                dtype = self.dtype_xdf_options[dtype_aux]
            else:
                raise ILDictionaryParseError(
                    f"The data type {dtype_aux} does not exist for the register: {identifier}"
                )

            # Access type
            access_aux = register.attrib["access"]
            access = None
            if access_aux in self.access_xdf_options:
                access = self.access_xdf_options[access_aux]
            else:
                raise ILDictionaryParseError(
                    f"The access type {access_aux} does not exist for the register: {identifier}"
                )

            # Address type
            address_type_aux = register.attrib["address_type"]

            if address_type_aux in self.address_type_xdf_options:
                address_type = self.address_type_xdf_options[address_type_aux]
            else:
                raise ILDictionaryParseError(
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
            range_elem = register.find(self.__DICT_RANGE)
            reg_range: Union[Tuple[None, None], Tuple[str, str]] = (None, None)
            if range_elem is not None:
                range_min = range_elem.attrib["min"]
                range_max = range_elem.attrib["max"]
                reg_range = (range_min, range_max)

            # Enumerations
            enums_elem = register.findall(self.__DICT_ENUMERATIONS_ENUMERATION)
            enums = {str(enum.text): int(enum.attrib["value"]) for enum in enums_elem}

            # Known bitfields.
            bitfields = None
            if identifier in self._KNOWN_REGISTER_BITFIELDS:
                bitfields = self._KNOWN_REGISTER_BITFIELDS[identifier]()

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
                bitfields=bitfields,
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

    def _append_missing_registers(
        self,
    ) -> None:
        """Append missing registers to the dictionary.

        Mainly registers needed for Monitoring/Disturbance and PDOs.

        """
        if self.__MON_DIST_STATUS_REGISTER in self._registers[0]:
            for register in self._MONITORING_DISTURBANCE_REGISTERS:
                if register.identifier is not None:
                    self._registers[register.subnode][register.identifier] = register
