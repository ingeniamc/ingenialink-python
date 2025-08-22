import copy
import enum
import math
import warnings
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Optional, Union
from xml.etree import ElementTree

import ingenialogger
from typing_extensions import override

from ingenialink.bitfield import BitField
from ingenialink.canopen.register import CanopenRegister
from ingenialink.enums.register import (
    RegAccess,
    RegAddressType,
    RegCyclicType,
    RegDtype,
)
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.ethernet.register import EthernetRegister
from ingenialink.exceptions import ILDictionaryParseError
from ingenialink.register import MonDistV3, Register
from ingenialink.utils._utils import weak_lru

logger = ingenialogger.get_logger(__name__)

# Dictionary constants guide:
# Each constant has this structure: DICT_ORIGIN_END
# ORIGIN: The start point of the path
# END: The end point of the path
# ORIGIN of LABELS
DICT_LABELS = "./Labels"
DICT_LABELS_LABEL = f"{DICT_LABELS}/Label"


ACCESS_XDF_OPTIONS: dict[str, RegAccess] = {
    "r": RegAccess.RO,
    "w": RegAccess.WO,
    "rw": RegAccess.RW,
}


DTYPE_XDF_OPTIONS: dict[str, RegDtype] = {
    "float": RegDtype.FLOAT,
    "s8": RegDtype.S8,
    "u8": RegDtype.U8,
    "s16": RegDtype.S16,
    "u16": RegDtype.U16,
    "s32": RegDtype.S32,
    "u32": RegDtype.U32,
    "s64": RegDtype.S64,
    "u64": RegDtype.U64,
    "str": RegDtype.STR,
    "bool": RegDtype.BOOL,
    "bit": RegDtype.BOOL,
    "byteArray512": RegDtype.BYTE_ARRAY_512,
}


class Interface(enum.Enum):
    """Connection Interfaces."""

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
    """Subnode types."""

    COMMUNICATION = enum.auto()
    """Communication"""
    MOTION = enum.auto()
    """Motion"""


class CanOpenObjectType(enum.Enum):
    """CanOpen Object Type."""

    VAR = enum.auto()
    """VAR object type"""

    RECORD = enum.auto()
    """RECORD object type"""

    ARRAY = enum.auto()
    """ARRAY object type"""


@dataclass()
class CanOpenObject:
    """CanOpenObject."""

    uid: str
    idx: int
    object_type: CanOpenObjectType
    registers: list[CanopenRegister]

    def __post_init__(self) -> None:
        """Post-initialization method."""
        # Ensure registers are sorted by subindex
        self.registers = sorted(self.registers, key=lambda obj: obj.subidx)

    def __iter__(self) -> Iterator[CanopenRegister]:
        """Iterator operator.

        Returns:
            Iterator operator.
        """
        return self.registers.__iter__()

    @property
    def bit_length(self) -> int:
        """Get the bit length of the object.

        Returns:
            int: bit length of the object.
        """
        bit_length = sum(register.bit_length for register in self.registers)
        if self.object_type in [CanOpenObjectType.ARRAY, CanOpenObjectType.RECORD]:
            # In arrays and records, between index 0 and 1 there's a padding of 8 bits
            bit_length += 8
        return bit_length

    @property
    def byte_length(self) -> int:
        """Get the byte length of the object.

        Returns:
            int: byte length of the object.
        """
        return math.ceil(self.bit_length / 8)


@dataclass
class DictionarySafetyPDO:
    """Safety PDOs dictionary descriptor."""

    @dataclass
    class PDORegister:
        """PDO register descriptor."""

        register: Optional[CanopenRegister]
        size: int

    index: int
    entries: list[PDORegister]


@dataclass
class DictionarySafetyModule:
    """Safety module (MDP) dictionary descriptor."""

    @dataclass
    class ApplicationParameter:
        """FSoE application parameter descriptor."""

        uid: str

    uses_sra: bool
    module_ident: int
    application_parameters: list[ApplicationParameter]


class DictionaryCategories:
    """Contains all categories from a Dictionary.

    Args:
        list_xdf_categories: List of Elements from xdf file

    """

    def __init__(self, list_xdf_categories: list[ElementTree.Element]) -> None:
        self._list_xdf_categories = list_xdf_categories
        self._cat_ids: list[str] = []
        self._categories: dict[str, dict[str, str]] = {}

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
    def category_ids(self) -> list[str]:
        """Category IDs."""
        return self._cat_ids

    def labels(self, cat_id: str) -> dict[str, str]:
        """Obtain labels for a certain category ID.

        Args:
        cat_id:  Category ID

        Returns:
            Labels dictionary.

        """
        return self._categories[cat_id]


@dataclass
class DictionaryError:
    """Class to store a dictionary error."""

    id: int
    """The error ID."""

    affected_module: str
    """The module affected by the error."""

    error_type: str
    """The error type."""

    description: Optional[str]
    """The error description."""

    def __iter__(self) -> Iterator[Union[str, None]]:
        """Iterator method.

        Returns:
            iterator method.
        """
        id_hex_string = f"0x{self.id:08X}"
        return iter((id_hex_string, self.affected_module, self.error_type, self.description))


@dataclass
class DictionaryDescriptor:
    """Class to store a dictionary error."""

    firmware_version: Optional[str] = None
    """Firmware version declared in the dictionary."""
    product_code: Optional[int] = None
    """Product code declared in the dictionary."""
    part_number: Optional[str] = None
    """Part number declared in the dictionary."""
    revision_number: Optional[int] = None
    """Revision number declared in the dictionary."""


class XMLBase(ABC):
    """Base class to manipulate XML files."""

    _CHECK_FAIL_EXCEPTION = Exception

    @classmethod
    def _findall_and_check(cls, root: ElementTree.Element, path: str) -> list[ElementTree.Element]:
        """Return list of elements in the target root element if existed, else, raises an exception.

        Args:
          root: root element
          path: target elements path

        Returns:
          list of path elements

        Raises:
          path elements not found

        """
        element = root.findall(path)
        if not element:
            raise cls._CHECK_FAIL_EXCEPTION(f"{path} element is not found")
        return element

    @classmethod
    def _find_and_check(cls, root: ElementTree.Element, path: str) -> ElementTree.Element:
        """Return the path element in the target root element if exists, else, raises an exception.

        Args:
            root: root element
            path: target element path

        Returns:
            path element

        Raises:
            path element not found

        """
        element = root.find(path)
        if element is None:
            raise cls._CHECK_FAIL_EXCEPTION(f"{path} element is not found")
        return element


class Dictionary(XMLBase, ABC):
    """Ingenia dictionary Abstract Base Class.

    Args:
        dictionary_path: Dictionary file path.
        interface: communication interface.

    Raises:
        ILDictionaryParseError: If the dictionary could not be created.

    """

    _CHECK_FAIL_EXCEPTION = ILDictionaryParseError

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
    subnodes: dict[int, SubnodeType]
    """Number of subnodes in the dictionary."""
    categories: DictionaryCategories
    """Instance of all the categories in the dictionary."""
    errors: dict[int, "DictionaryError"]
    """Instance of all the errors in the dictionary."""
    image: Optional[str] = None
    """Drive's encoded image."""
    is_safe: bool = False
    """True if has SafetyPDOs element, else False"""
    _registers: dict[int, dict[str, Register]]
    """Instance of all the registers in the dictionary"""
    items: dict[int, dict[str, CanOpenObject]]
    """Registers group by subnode and UID"""
    safety_rpdos: dict[str, DictionarySafetyPDO]
    """Safety RPDOs by UID"""
    safety_tpdos: dict[str, DictionarySafetyPDO]
    """Safety TPDOs by UID"""
    safety_modules: dict[int, DictionarySafetyModule]
    """Safety modules (MDP)."""

    def __init__(self, dictionary_path: str, interface: Interface) -> None:
        self.items = {}
        self.safety_rpdos = {}
        self.safety_tpdos = {}
        self.safety_modules = {}
        self._registers = {}
        self.subnodes = {}
        self.path = dictionary_path
        """Path of the dictionary."""
        self.interface = interface
        try:
            self.read_dictionary()
        except KeyError as e:
            raise ILDictionaryParseError("The dictionary is not well-formed.") from e

    @staticmethod
    def _get_address_type_xdf_options(address_type: str) -> RegAddressType:
        """Returns the address type associated with a string.

        Args:
            address_type: address type.

        Raises:
            ILDictionaryParseError: if the provided address type does not exist.

        Returns:
            Address type.
        """
        if address_type == "NVM":
            return RegAddressType.NVM
        if address_type == "NVM_NONE":
            return RegAddressType.NVM_NONE
        if address_type == "NVM_CFG":
            return RegAddressType.NVM_CFG
        if address_type == "NVM_LOCK":
            return RegAddressType.NVM_LOCK
        if address_type == "NVM_HW":
            return RegAddressType.NVM_HW
        if address_type == "NVM_INDIRECT":
            return RegAddressType.NVM_INDIRECT
        raise ILDictionaryParseError(f"The address type {address_type} does not exist.")

    @staticmethod
    def _get_subnode_xdf_options(subnode: str) -> SubnodeType:
        """Returns the `SubnodeType` corresponding to a subnode string.

        Args:
            subnode: subnode.

        Raises:
            ILDictionaryParseError: if the provided subnode has no `SubnodeType` associated with.

        Returns:
            subnode type.
        """
        if subnode == "Communication":
            return SubnodeType.COMMUNICATION
        if subnode == "Motion":
            return SubnodeType.MOTION
        raise ILDictionaryParseError(f"{subnode=} does not exist.")

    @classmethod
    @abstractmethod
    def get_description(cls, dictionary_path: str, interface: Interface) -> DictionaryDescriptor:
        """Quick function to get target dictionary description.

        Args:
            dictionary_path: target dictionary path
            interface: device interface

        Returns:
            Target dictionary description
        """

    def __add__(self, other_dict: "Dictionary") -> "Dictionary":
        """Merge two dictionary instances.

        It can only be used for merging COM-KIT and CORE dictionaries.

        Raises:
            TypeError: If dictionaries cannot be merged because of the type.
            ValueError: If the dictionaries cannot be merged because none of them
                is a COM-KIT dictionary.

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

    def registers(self, subnode: int) -> dict[str, Register]:
        """Gets the register dictionary to the targeted subnode.

        Args:
            subnode: Identifier for the subnode.

        Returns:
            Dictionary of all the registers for a subnode.

        """
        return self._registers[subnode]

    def all_registers(self) -> Iterator[Register]:
        """Iterator for all registers.

        Yields:
            Register
        """
        for subnode in self._registers.values():
            yield from subnode.values()

    def all_objs(self) -> Iterator[CanOpenObject]:
        """Iterator for all items.

        Yields:
            CanOpenObject
        """
        for subnode in self.items.values():
            yield from subnode.values()

    @weak_lru()
    def get_register(self, uid: str, axis: Optional[int] = None) -> Register:
        """Gets the targeted register.

        Args:
            uid: register uid.
            axis: axis. Should be specified if multiaxis, None otherwise.

        Raises:
            KeyError: if the specified axis does not exist.
            KeyError: if the register is not present in the specified axis.
            ValueError: if the register is not found in any axis, if axis is not provided.
            ValueError: if the register is found in multiple axis, if axis is provided.

        Returns:
            register.
        """
        if axis is not None:
            if axis not in self._registers:
                raise KeyError(f"{axis=} does not exist.")
            registers = self.registers(axis)
            if uid not in registers:
                raise KeyError(f"Register {uid} not present in {axis=}")
            return registers[uid]

        matching_registers: list[Register] = []
        for axis in self.subnodes:
            axis_registers = self.registers(axis)
            if uid in axis_registers:
                matching_registers.append(axis_registers[uid])

        if len(matching_registers) == 0:
            raise ValueError(f"Register {uid} not found.")
        if len(matching_registers) > 1:
            raise ValueError(f"Register {uid} found in multiple axis. Axis should be specified.")

        return matching_registers[0]

    @abstractmethod
    def read_dictionary(self) -> None:
        """Reads the dictionary file and initializes all its components."""

    def get_object(self, uid: str, subnode: Optional[int] = None) -> CanOpenObject:
        """Return object by an UID and subnode.

        Args:
            uid: object UID
            subnode: object subnode

        Returns:
            CanOpen Object

        Raises:
            KeyError: Object does not exist

        """
        if subnode is None:
            subnode = 0
        if subnode in self.items and uid in self.items[subnode]:
            return self.items[subnode][uid]
        raise KeyError(f"Object {uid} in subnode {subnode} not exist")

    def get_safety_rpdo(self, uid: str) -> DictionarySafetyPDO:
        """Get Safe RPDO by uid.

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
        """Get Safe TPDO by uid.

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

    def get_safety_module(self, module_ident: Union[int, str]) -> DictionarySafetyModule:
        """Get safety module by module_ident.

        Args:
            module_ident: safety module module ident (int/hex).

        Returns:
            Safety module object description.

        Raises:
            NotImplementedError: Device is not safe.
            KeyError: Safety module does not exist.
        """
        if not self.is_safe:
            raise NotImplementedError("Safety modules are not implemented for this device")
        if isinstance(module_ident, str):
            module_ident = int(module_ident, 16)
        if module_ident in self.safety_modules:
            return self.safety_modules[module_ident]
        raise KeyError(f"Safety Module {module_ident} not exist")

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
        """Merge dictionary attributes.

        Add the revision number, product code, firmware version and part number

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

    def _read_errors(self, root: ElementTree.Element, path: str) -> None:
        """Process Errors element and set errors.

        Args:
            root: Errors element
            path: The error path.

        """
        error_list = self._findall_and_check(root, path)
        self._load_errors(error_list)

    @staticmethod
    def _findall_and_check(root: ElementTree.Element, path: str) -> list[ElementTree.Element]:
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

    def _load_errors(self, error_list: list[ElementTree.Element]) -> None:
        """Parse and load the errors into the errors dictionary."""
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
        """Check if dictionary is a CoCo dictionary.

        Returns:
            True if the dictionary is a CoCo dictionary. False otherwise.

        """
        return len(self.registers(1)) == 0


class DictionaryV3(Dictionary):
    """Class to represent a Dictionary V3."""

    __DRIVE_IMAGE_ELEMENT = "DriveImage"

    __HEADER_ELEMENT = "Header"
    __VERSION_ELEMENT = "Version"

    __BODY_ELEMENT = "Body"

    __CATEGORIES_ELEMENT = "Categories"
    __CATEGORY_ELEMENT = "Category"

    __DEVICES_ELEMENT = "Devices"

    __DEVICE_FW_VERSION_ATTR = "firmwareVersion"
    __DEVICE_PRODUCT_CODE_ATTR = "ProductCode"
    __DEVICE_PART_NUMBER_ATTR = "PartNumber"
    DEVICE_REVISION_NUMBER_ATTR = "RevisionNumber"

    __SUBNODES_ELEMENT = "Subnodes"
    __SUBNODE_ELEMENT = "Subnode"
    __SUBNODE_INDEX_ATTR = "index"

    __SUBNODE_ATTR = "subnode"
    __OBJECT_DATA_TYPE_ATTR = "datatype"
    __ADDRESS_TYPE_ATTR = "address_type"
    __ACCESS_ATTR = "access"
    __DTYPE_ATTR = "dtype"
    __UID_ATTR = "id"
    __PDO_ACCESS_ATTR = "pdo_access"
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
    __AXIS_ATTR = "axis"

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

    __MONITORING_ELEMENT = "MonDistV3"
    __MONITORING_ADDRESS_ATTR = "address"
    __MONITORING_SUBNODE_ATTR = "subnode"
    __MONITORING_CYCLIC_ATTR = "cyclic"

    __SAFETY_PDOS_ELEMENT = "SafetyPDOs"
    __RPDO_ELEMENT = "RPDO"
    __TPDO_ELEMENT = "TPDO"
    __PDO_UID_ATTR = "id"
    __PDO_INDEX_ATTR = "index"
    __PDO_ENTRY_ELEMENT = "PDOEntry"
    __PDO_ENTRY_SIZE_ATTR = "size"
    __PDO_ENTRY_SUBNODE_ATTR = "subnode"

    __SAFETY_MODULES_ELEMENT = "SafetyModules"
    __SAFETY_MODULE_ELEMENT = "SafetyModule"
    __SAFETY_MODULE_USES_SRA_ATTR = "uses_sra"
    __SAFETY_MODULE_MODULE_IDENT_ATTR = "module_ident"
    __APPLICATION_PARAMETERS_ELEMENT = "ApplicationParameters"
    __APPLICATION_PARAMETER_ELEMENT = "ApplicationParameter"
    __APPLICATION_PARAMETER_UID_ATTR = "id"

    def __init__(self, dictionary_path: str, interface: Optional[Interface] = None) -> None:
        """Initialize the DictionaryV3 instance.

        Args:
            dictionary_path: Path to the Ingenia dictionary.
            interface: communication interface for retro compatibility,
                specific classes should be used instead of this argument.

        """
        if self.__class__ is DictionaryV3 or interface:
            warnings.warn(
                "Using DictionaryV3 as an instance classis deprecated, "
                "use a specific class instead, like EthercatDictionaryV3",
                DeprecationWarning,
                stacklevel=2,
            )

        if interface is None:
            interface = self.interface

        super().__init__(dictionary_path, interface)

    @staticmethod
    def _interface_to_device_element(interface: Interface) -> str:
        """Returns the device element associated with each interface.

        Args:
            interface: interface.

        Raises:
            ILDictionaryParseError: if the interface doesn't have any device element associated.

        Returns:
            Device element.
        """
        if interface is Interface.CAN:
            return "CANDevice"
        if interface is Interface.ETH:
            return "ETHDevice"
        if interface is Interface.ECAT:
            return "ECATDevice"
        if interface is Interface.EoE:
            return "EoEDevice"
        raise ILDictionaryParseError(f"{interface=} has no device element associated.")

    @staticmethod
    def _get_canopen_object_data_type_options(data_type: str) -> CanOpenObjectType:
        """Returns the `CanOpenObjectType` corresponding to a data type string.

        Args:
            data_type: data type.

        Raises:
            ILDictionaryParseError: if the provided data type has no `CanOpenObjectType` associated.

        Returns:
            subnode type.
        """
        if data_type == "VAR":
            return CanOpenObjectType.VAR
        if data_type == "RECORD":
            return CanOpenObjectType.RECORD
        if data_type == "ARRAY":
            return CanOpenObjectType.ARRAY
        raise ILDictionaryParseError(f"{data_type} has no canopen object type associated.")

    @override
    @classmethod
    def get_description(cls, dictionary_path: str, interface: Interface) -> DictionaryDescriptor:
        try:
            with open(dictionary_path, encoding="utf-8") as xdf_file:
                tree = ElementTree.parse(xdf_file)
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"There is not any xdf file in the path: {dictionary_path}"
            ) from e
        root = tree.getroot()
        device_path = (
            f"{cls.__BODY_ELEMENT}/{cls.__DEVICES_ELEMENT}/"
            f"{DictionaryV3._interface_to_device_element(interface)}"
        )
        device = root.find(device_path)
        if device is None:
            raise ILDictionaryParseError("Dictionary cannot be used for the chosen communication")
        firmware_version = device.attrib[cls.__DEVICE_FW_VERSION_ATTR]
        product_code = int(device.attrib[cls.__DEVICE_PRODUCT_CODE_ATTR])
        part_number = device.attrib[cls.__DEVICE_PART_NUMBER_ATTR]
        revision_number = int(device.attrib[cls.DEVICE_REVISION_NUMBER_ATTR])
        return DictionaryDescriptor(firmware_version, product_code, part_number, revision_number)

    @override
    def read_dictionary(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as xdf_file:
                tree = ElementTree.parse(xdf_file)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"There is not any xdf file in the path: {self.path}") from e
        root = tree.getroot()
        drive_image_element = self._find_and_check(root, self.__DRIVE_IMAGE_ELEMENT)
        self.__read_drive_image(drive_image_element)
        header_element = self._find_and_check(root, self.__HEADER_ELEMENT)
        self.__read_header(header_element)
        body_element = self._find_and_check(root, self.__BODY_ELEMENT)
        self.__read_body(body_element)

    def __read_drive_image(self, drive_image: ElementTree.Element) -> None:
        """Process DriveImage element and set image.

        Args:
            drive_image: DriveImage element

        """
        if drive_image.text is not None and drive_image.text.strip():
            self.image = drive_image.text.strip()
        else:
            self.image = None

    def __read_header(self, root: ElementTree.Element) -> None:
        """Process Header element.

        Args:
            root: Header element

        """
        version_element = self._find_and_check(root, self.__VERSION_ELEMENT)
        self.__read_version(version_element)
        # Dictionary localization not implemented

    def __read_version(self, root: ElementTree.Element) -> None:
        """Process Version element and set version.

        Args:
            root: Version element

        Raises:
            ILDictionaryParseError: version is empty

        """
        if root.text is None:
            raise ILDictionaryParseError("Version is empty")
        self.version = root.text.strip()

    def __read_body(self, root: ElementTree.Element) -> None:
        """Process Body element.

        Args:
            root: Body element

        """
        categories_element = self._find_and_check(root, self.__CATEGORIES_ELEMENT)
        self.__read_categories(categories_element)
        devices_element = self._find_and_check(root, self.__DEVICES_ELEMENT)
        self.__read_devices(devices_element)

    def __read_categories(self, root: ElementTree.Element) -> None:
        """Process Categories element and set categories.

        Args:
            root: Categories element

        """
        category_list = self._findall_and_check(root, self.__CATEGORY_ELEMENT)
        self.categories = DictionaryCategories(category_list)

    def __read_devices(self, root: ElementTree.Element) -> None:
        """Process Devices element.

        Args:
            root: Devices element

        Raises:
            ILDictionaryParseError: If the dictionary cannot be used for the chosen communication.
        """
        if self.interface == Interface.VIRTUAL:
            device_element = root.find(DictionaryV3._interface_to_device_element(Interface.ETH))
            if device_element is None:
                device_element = root.find(DictionaryV3._interface_to_device_element(Interface.EoE))
                self.interface = Interface.EoE
            else:
                self.interface = Interface.ETH
        else:
            device_element = root.find(DictionaryV3._interface_to_device_element(self.interface))
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

    def __read_device_attributes(self, device: ElementTree.Element) -> None:
        self.firmware_version = device.attrib[self.__DEVICE_FW_VERSION_ATTR]
        self.product_code = int(device.attrib[self.__DEVICE_PRODUCT_CODE_ATTR])
        self.part_number = device.attrib[self.__DEVICE_PART_NUMBER_ATTR]
        self.revision_number = int(device.attrib[self.DEVICE_REVISION_NUMBER_ATTR])

    def __read_device_eoe(self, root: ElementTree.Element) -> None:
        """Process EoEDevice element.

        Args:
            root: EoEDevice element

        """
        # Device element is identical
        self.__read_device_eth(root)

    def __read_device_eth(self, root: ElementTree.Element) -> None:
        """Process ETHDevice element.

        Args:
            root: ETHDevice element

        """
        subnodes_element = self._find_and_check(root, self.__SUBNODES_ELEMENT)
        self.__read_subnodes(subnodes_element)
        registers_element = self._find_and_check(root, self.__MCB_REGISTERS_ELEMENT)
        register_element_list = self._findall_and_check(
            registers_element, self.__MCB_REGISTER_ELEMENT
        )
        for register_element in register_element_list:
            self.__read_mcb_register(register_element)
        errors_element = self._find_and_check(root, self.__ERRORS_ELEMENT)
        self._read_errors(errors_element, self.__ERROR_ELEMENT)

    def __read_device_ecat(self, root: ElementTree.Element) -> None:
        """Process ECATDevice element.

        Args:
            root: ECATDevice element

        """
        registers_element = self._find_and_check(root, self.__CANOPEN_OBJECTS_ELEMENT)
        register_element_list = self._findall_and_check(
            registers_element, self.__CANOPEN_OBJECT_ELEMENT
        )
        for register_element in register_element_list:
            self.__read_canopen_object(register_element)
        errors_element = self._find_and_check(root, self.__ERRORS_ELEMENT)
        self._read_errors(errors_element, self.__ERROR_ELEMENT)
        safety_pdos_element = root.find(self.__SAFETY_PDOS_ELEMENT)
        if safety_pdos_element is not None:
            self.__read_safety_pdos(safety_pdos_element)
        safety_modules_element = root.find(self.__SAFETY_MODULES_ELEMENT)
        if safety_modules_element is not None:
            self.__read_safety_modules(safety_modules_element)

    def __read_device_can(self, root: ElementTree.Element) -> None:
        """Process CANDevice element.

        Args:
            root: CANDevice element

        """
        registers_element = self._find_and_check(root, self.__CANOPEN_OBJECTS_ELEMENT)
        register_element_list = self._findall_and_check(
            registers_element, self.__CANOPEN_OBJECT_ELEMENT
        )
        for register_element in register_element_list:
            self.__read_canopen_object(register_element)
        errors_element = self._find_and_check(root, self.__ERRORS_ELEMENT)
        self._read_errors(errors_element, self.__ERROR_ELEMENT)

    def __read_subnodes(self, root: ElementTree.Element) -> None:
        """Process Subnodes element and fill subnodes.

        Args:
            root: Subnodes element

        Raises:
            ILDictionaryParseError: Subnode element text is None

        """
        subnode_list = self._findall_and_check(root, self.__SUBNODE_ELEMENT)
        for subnode in subnode_list:
            if subnode.text is None:
                raise ILDictionaryParseError("Subnode element text is None")
            self.subnodes[int(subnode.attrib[self.__SUBNODE_INDEX_ATTR])] = (
                Dictionary._get_subnode_xdf_options(subnode.text.strip())
            )

    def __read_labels(self, root: ElementTree.Element) -> dict[str, str]:
        """Process Labels element.

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

    def __read_label(self, label: ElementTree.Element) -> tuple[str, str]:
        """Process Label element.

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
        self, range_elem: Optional[ElementTree.Element]
    ) -> Union[tuple[None, None], tuple[str, str]]:
        """Process Range element.

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

    def __read_monitoring(
        self, monitoring_elem: Optional[ElementTree.Element]
    ) -> Optional[MonDistV3]:
        """Process Monitoring element.

        Args:
            monitoring_elem: Monitoring element.

        Returns:
            Monitoring data, None if the register is not monitoreable.
        """
        if monitoring_elem is None:
            return None

        return MonDistV3(
            address=int(monitoring_elem.attrib[self.__MONITORING_ADDRESS_ATTR], 16),
            subnode=int(monitoring_elem.attrib[self.__MONITORING_SUBNODE_ATTR]),
            cyclic=RegCyclicType(monitoring_elem.attrib[self.__MONITORING_CYCLIC_ATTR]),
        )

    def __read_enumeration(
        self, enumerations_element: Optional[ElementTree.Element]
    ) -> Optional[dict[str, int]]:
        """Process Enumerations possible element.

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
        self, bitfields_element: Optional[ElementTree.Element]
    ) -> Optional[dict[str, BitField]]:
        """Process Bitfields possible element.

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

    def __add_register(self, register: Register, axis: int) -> None:
        """Adds a register to register list.

        Args:
            register: register to add.
            axis: register's axis.

        Raises:
            ValueError: if register identifier is not provided.
        """
        if axis not in self._registers:
            self._registers[axis] = {}
            if axis == 0:
                self.subnodes[axis] = SubnodeType.COMMUNICATION
            else:
                self.subnodes[axis] = SubnodeType.MOTION
        if register.identifier is None:
            raise ValueError("Identifier must be provided.")
        self._registers[axis][register.identifier] = register

    def __read_mcb_register(self, register: ElementTree.Element) -> None:
        """Process MCBRegister element and add it to _registers.

        Args:
            register: MCBRegister element

        """
        reg_address = int(register.attrib[self.__ADDRESS_ATTR], 16)
        subnode = int(register.attrib[self.__SUBNODE_ATTR])
        address_type = Dictionary._get_address_type_xdf_options(
            register.attrib[self.__ADDRESS_TYPE_ATTR]
        )
        access = ACCESS_XDF_OPTIONS[register.attrib[self.__ACCESS_ATTR]]
        dtype = DTYPE_XDF_OPTIONS[register.attrib[self.__DTYPE_ATTR]]
        identifier = register.attrib[self.__UID_ATTR]
        pdo_access = RegCyclicType(register.attrib[self.__PDO_ACCESS_ATTR])
        description = register.attrib[self.__DESCRIPTION_ATTR]
        default = bytes.fromhex(register.attrib[self.__DEFAULT_ATTR])
        cat_id = register.attrib[self.__CAT_ID_ATTR]
        units = register.attrib.get(self.__UNITS_ATTR)
        # Labels
        labels_element = self._find_and_check(register, self.__LABELS_ELEMENT)
        labels = self.__read_labels(labels_element)
        # Range
        range_elem = register.find(self.__RANGE_ELEMENT)
        reg_range = self.__read_range(range_elem)
        # Monitoring
        monitoring_elem = register.find(self.__MONITORING_ELEMENT)
        monitoring = self.__read_monitoring(monitoring_elem)
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
            pdo_access=pdo_access,
            subnode=subnode,
            reg_range=reg_range,
            labels=labels,
            enums=enums,
            cat_id=cat_id,
            address_type=address_type,
            description=description,
            default=default,
            bitfields=bitfields,
            monitoring=monitoring,
        )
        self.__add_register(register=ethernet_register, axis=subnode)

    def __read_canopen_object(self, root: ElementTree.Element) -> None:
        """Process CANopenObject element and add it to registers_group if has UID.

        Args:
            root: CANopenObject element

        """
        object_uid = root.attrib.get(self.__UID_ATTR)
        obj_index = int(root.attrib[self.__INDEX_ATTR], 16)
        axis = int(root.attrib[self.__AXIS_ATTR]) if self.__AXIS_ATTR in root.attrib else 0
        data_type = DictionaryV3._get_canopen_object_data_type_options(
            root.attrib[self.__OBJECT_DATA_TYPE_ATTR]
        )
        subitems_element = self._find_and_check(root, self.__SUBITEMS_ELEMENT)
        subitem_list = self._findall_and_check(subitems_element, self.__SUBITEM_ELEMENT)
        register_list = [
            self.__read_canopen_subitem(subitem, obj_index, axis) for subitem in subitem_list
        ]
        if object_uid:
            register_list.sort(key=lambda val: val.subidx)
            if axis not in self.items:
                self.items[axis] = {}
            self.items[axis][object_uid] = CanOpenObject(
                object_uid, obj_index, data_type, register_list
            )

    def __read_canopen_subitem(
        self, subitem: ElementTree.Element, reg_index: int, subnode: int
    ) -> Union[CanopenRegister, EthercatRegister]:
        """Process Subitem element and add it to _registers.

        Args:
            subitem: CANopenObject element
            reg_index: register index
            subnode: register subnode

        Returns:
            Subitem register

        Raises:
            ValueError: if Canopen/Ethercat register cannot be created for
                the communication interface.
        """
        reg_subindex: int = int(subitem.attrib[self.__SUBINDEX_ATTR])
        address_type = Dictionary._get_address_type_xdf_options(
            subitem.attrib[self.__ADDRESS_TYPE_ATTR]
        )
        access = ACCESS_XDF_OPTIONS[subitem.attrib[self.__ACCESS_ATTR]]
        dtype = DTYPE_XDF_OPTIONS[subitem.attrib[self.__DTYPE_ATTR]]
        identifier = subitem.attrib[self.__UID_ATTR]
        pdo_access = RegCyclicType(subitem.attrib[self.__PDO_ACCESS_ATTR])
        description = subitem.attrib[self.__DESCRIPTION_ATTR]
        default = bytes.fromhex(subitem.attrib[self.__DEFAULT_ATTR])
        cat_id = subitem.attrib[self.__CAT_ID_ATTR]
        units = subitem.attrib.get(self.__UNITS_ATTR)
        is_node_id_dependent = (
            subitem.attrib.get(self.__IS_NODE_ID_DEPENDENT_ATTR)
            == self.__IS_NODE_ID_DEPENDENT_TRUE_ATTR_VALUE
        )
        # Labels
        labels_element = self._find_and_check(subitem, self.__LABELS_ELEMENT)
        labels = self.__read_labels(labels_element)
        # Range
        range_elem = subitem.find(self.__RANGE_ELEMENT)
        reg_range = self.__read_range(range_elem)
        # Monitoring
        monitoring_elem = subitem.find(self.__MONITORING_ELEMENT)
        monitoring = self.__read_monitoring(monitoring_elem)
        # Enumerations
        enumerations_element = subitem.find(self.__ENUMERATIONS_ELEMENT)
        enums = self.__read_enumeration(enumerations_element)
        # Bitfields
        bitfields_element = subitem.find(self.__BITFIELDS_ELEMENT)
        bitfields = self.__read_bitfields(bitfields_element)

        if self.interface == Interface.CAN:
            register_instance = CanopenRegister
        elif self.interface == Interface.ECAT:
            register_instance = EthercatRegister
        else:
            raise ValueError(
                f"Cannot create Canopen/Ethercat register for interface {self.interface}"
            )

        reg = register_instance(
            idx=reg_index,
            subidx=reg_subindex,
            dtype=dtype,
            access=access,
            identifier=identifier,
            units=units,
            pdo_access=pdo_access,
            subnode=subnode,
            reg_range=reg_range,
            labels=labels,
            enums=enums,
            cat_id=cat_id,
            address_type=address_type,
            description=description,
            default=default,
            bitfields=bitfields,
            monitoring=monitoring,
            is_node_id_dependent=is_node_id_dependent,
        )
        self.__add_register(register=reg, axis=subnode)
        return reg

    def __read_safety_pdos(self, root: ElementTree.Element) -> None:
        """Process SafetyPDOs element.

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

    def __read_pdo(self, pdo: ElementTree.Element) -> tuple[str, DictionarySafetyPDO]:
        """Process RPDO and TPDO elements.

        Args:
            pdo: MCBRegister element

        Returns:
            PDO uid and class description

        Raises:
            ILDictionaryParseError: PDO register does not exist
            ValueError: If the subnode is not a CANopen register.
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

    def __read_safety_modules(self, root: ElementTree.Element) -> None:
        """Process SafetyModules element.

        Args:
            root: SafetyModules element.
        """
        self.is_safe = True
        safety_modules_list = self._findall_and_check(root, self.__SAFETY_MODULE_ELEMENT)
        for safety_module_element in safety_modules_list:
            module_ident, safety_module = self.__read_safety_module(
                safety_module=safety_module_element
            )
            self.safety_modules[module_ident] = safety_module

    def __read_safety_module(
        self, safety_module: ElementTree.Element
    ) -> tuple[int, DictionarySafetyModule]:
        """Process SafetyModule element.

        Args:
            safety_module: SafetyModule element.

        Returns:
            Safety module ident and class descriptor.
        """
        uses_sra = safety_module.attrib[self.__SAFETY_MODULE_USES_SRA_ATTR] in [
            "True",
            "true",
        ]
        module_ident = int(safety_module.attrib[self.__SAFETY_MODULE_MODULE_IDENT_ATTR], 16)
        application_parameters_element = self._find_and_check(
            safety_module, self.__APPLICATION_PARAMETERS_ELEMENT
        )
        application_parameters_list = self._findall_and_check(
            application_parameters_element, self.__APPLICATION_PARAMETER_ELEMENT
        )
        application_parameters = [
            DictionarySafetyModule.ApplicationParameter(
                uid=param.attrib[self.__APPLICATION_PARAMETER_UID_ATTR]
            )
            for param in application_parameters_list
        ]
        return module_ident, DictionarySafetyModule(
            uses_sra=uses_sra,
            module_ident=module_ident,
            application_parameters=application_parameters,
        )


class DictionaryV2(Dictionary):
    """Class to represent a Dictionary V2."""

    # Dictionary constants guide:
    # Each constant has this structure: DICT_ORIGIN_END
    # ORIGIN: The start point of the path
    # END: The end point of the path
    # ORIGIN of ROOT
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
    # ORIGIN of REGISTERS
    __DICT_REGISTERS = "./Registers"
    __DICT_REGISTERS_REGISTER = f"{__DICT_REGISTERS}/Register"
    # ORIGIN of RANGE
    __DICT_RANGE = "./Range"
    # ORIGIN of ENUMERATIONS
    __DICT_ENUMERATIONS = "./Enumerations"
    __DICT_ENUMERATIONS_ENUMERATION = f"{__DICT_ENUMERATIONS}/Enum"
    __DICT_IMAGE = "DriveImage"

    dict_interface: Optional[str]

    __MON_DIST_STATUS_REGISTER = "MON_DIST_STATUS"

    def __init__(self, dictionary_path: str) -> None:
        super().__init__(dictionary_path, self.interface)

    @staticmethod
    def _interface_to_str(interface: Interface) -> str:
        """Returns the string associated with each interface.

        Args:
            interface: interface.

        Raises:
            ILDictionaryParseError: if the interface doesn't have any string associated.

        Returns:
            Interface string.
        """
        if interface is Interface.CAN:
            return "CAN"
        if interface in [Interface.ECAT, Interface.EoE, Interface.ETH]:
            return "ETH"
        raise ILDictionaryParseError(f"{interface=} has no string associated.")

    @cached_property
    def __drv_state_status_known_bitfields(self) -> dict[str, BitField]:
        return {
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
        }

    @cached_property
    def __drv_state_control(self) -> dict[str, BitField]:
        return {
            # https://drives.novantamotion.com/summit/0x010-control-word
            "SWITCH_ON": BitField.bit(0),
            "VOLTAGE_ENABLE": BitField.bit(1),
            "QUICK_STOP": BitField.bit(2),
            "ENABLE_OPERATION": BitField.bit(3),
            "RUN_SET_POINT_MANAGER": BitField.bit(4),
            "FAULT_RESET": BitField.bit(7),
        }

    @cached_property
    def __drv_op_cmd(self) -> dict[str, BitField]:
        return {
            # https://drives.novantamotion.com/summit/0x014-operation-mode
            "OPERATION_MODE": BitField(0, 3),
            "PROFILER_MODE": BitField(4, 6),
            "PTP_BUFFER": BitField.bit(7),
            "HOMING": BitField.bit(8),
        }

    @cached_property
    def __drv_prot_sto_status(self) -> dict[str, BitField]:
        return {
            # https://drives.novantamotion.com/summit/0x51a-sto-status
            "STO1": BitField.bit(0),
            "STO2": BitField.bit(1),
            "STO_SUPPLY_FAULT": BitField.bit(2),
            "STO_ABNORMAL_FAULT": BitField.bit(3),
            "STO_REPORT": BitField.bit(4),
        }

    def _get_known_register_bitfields(self, register: str) -> Optional[dict[str, BitField]]:
        """Gets the known register bitfields.

        Args:
            register: register.

        Returns:
            Register bitfields, None if the bitfields are unknown.
        """
        if register == "DRV_STATE_STATUS":
            return self.__drv_state_status_known_bitfields
        if register == "DRV_STATE_CONTROL":
            return self.__drv_state_control
        if register == "DRV_OP_CMD":
            return self.__drv_op_cmd
        if register == "DRV_PROT_STO_STATUS":
            return self.__drv_prot_sto_status
        return None

    @property
    @abstractmethod
    def _monitoring_disturbance_registers(
        self,
    ) -> Union[list[EthercatRegister], list[EthernetRegister], list[CanopenRegister]]:
        raise NotImplementedError

    @property
    @abstractmethod
    def _safety_registers(
        self,
    ) -> list[EthercatRegister]:
        raise NotImplementedError

    @property
    @abstractmethod
    def _safety_modules(self) -> list[DictionarySafetyModule]:
        raise NotImplementedError

    @override
    @classmethod
    def get_description(cls, dictionary_path: str, interface: Interface) -> DictionaryDescriptor:
        try:
            with open(dictionary_path, encoding="utf-8") as xdf_file:
                tree = ElementTree.parse(xdf_file)
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
        if (
            DictionaryV2._interface_to_str(interface) != dict_interface
            and dict_interface is not None
        ):
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

    @override
    def read_dictionary(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as xdf_file:
                tree = ElementTree.parse(xdf_file)
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
            and DictionaryV2._interface_to_str(self.interface) != self.dict_interface
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

    def _read_xdf_register(self, register: ElementTree.Element) -> Optional[Register]:
        """Reads a register from the dictionary and creates a Register instance.

        Args:
            register: Register instance from the dictionary.

        Returns:
            The current register which it has been reading
            None: When at least a mandatory attribute is not in a xdf file

        Raises:
            ILDictionaryParseError: If the register data type is invalid.
            ILDictionaryParseError: If the register access type is invalid.
        """
        try:
            identifier = register.attrib["id"]
        except KeyError as ke:
            logger.error(f"The register doesn't have an identifier. Error caught: {ke}")
            return None

        try:
            units = register.attrib["units"]
            pdo_access = RegCyclicType(register.attrib.get("cyclic", "CONFIG"))

            # Data type
            dtype_aux = register.attrib["dtype"]
            dtype = None
            if dtype_aux in DTYPE_XDF_OPTIONS:
                dtype = DTYPE_XDF_OPTIONS[dtype_aux]
            else:
                raise ILDictionaryParseError(
                    f"The data type {dtype_aux} does not exist for the register: {identifier}"
                )

            # Access type
            access_aux = register.attrib["access"]
            access = None
            if access_aux in ACCESS_XDF_OPTIONS:
                access = ACCESS_XDF_OPTIONS[access_aux]
            else:
                raise ILDictionaryParseError(
                    f"The access type {access_aux} does not exist for the register: {identifier}"
                )

            # Address type
            address_type = Dictionary._get_address_type_xdf_options(register.attrib["address_type"])

            subnode = int(register.attrib.get("subnode", 1))
            storage = register.attrib.get("storage")
            cat_id = register.attrib.get("cat_id")
            internal_use = int(register.attrib.get("internal_use", 0))

            # Labels
            labels_elem = register.findall(DICT_LABELS_LABEL)
            labels = {label.attrib["lang"]: str(label.text) for label in labels_elem}

            # Range
            range_elem = register.find(self.__DICT_RANGE)
            reg_range: Union[tuple[None, None], tuple[str, str]] = (None, None)
            if range_elem is not None:
                range_min = range_elem.attrib["min"]
                range_max = range_elem.attrib["max"]
                reg_range = (range_min, range_max)

            # Enumerations
            enums_elem = register.findall(self.__DICT_ENUMERATIONS_ENUMERATION)
            enums = {str(enum.text): int(enum.attrib["value"]) for enum in enums_elem}

            # Known bitfields.
            bitfields = self._get_known_register_bitfields(identifier)

            description = register.attrib.get("desc")

            current_read_register = Register(
                dtype,
                access,
                identifier=identifier,
                units=units,
                pdo_access=pdo_access,
                subnode=subnode,
                storage=storage,
                reg_range=reg_range,
                labels=labels,
                enums=enums,
                cat_id=cat_id,
                internal_use=internal_use,
                address_type=address_type,
                bitfields=bitfields,
                description=description,
            )

            return current_read_register

        except KeyError as ke:
            logger.error(f"Register with ID {identifier} has not attribute {ke}")
            return None

    def _add_register_list(
        self,
        register: Register,
    ) -> None:
        """Adds the current read register into the _registers list.

        Args:
            register: the current read register it will be instanced

        """
        identifier = register.identifier
        subnode = register.subnode
        if identifier is None:
            return
        # Check category
        register.cat_id = register.cat_id or "UNCATEGORIZED"
        category = register.cat_id
        if category not in self.categories.category_ids:
            self.categories._cat_ids.append(category)
            self.categories._categories[category] = {"en_US": category.capitalize()}
        self._registers[subnode][identifier] = register

    def _append_missing_registers(
        self,
    ) -> None:
        """Append missing registers to the dictionary.

        Mainly registers needed for Monitoring/Disturbance and PDOs.

        """
        if self.__MON_DIST_STATUS_REGISTER in self._registers[0]:
            for register in self._monitoring_disturbance_registers:
                self._add_register_list(register)
