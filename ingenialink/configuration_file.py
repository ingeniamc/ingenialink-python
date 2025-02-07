import os
import re
from abc import ABC
from typing import Optional, Union
from xml.dom import minidom
from xml.etree import ElementTree

import ingenialogger
import numpy as np

from ingenialink import RegAccess, RegDtype
from ingenialink.dictionary import Dictionary, Interface
from ingenialink.exceptions import ILConfigurationFileParseError
from ingenialink.register import Register

logger = ingenialogger.get_logger(__name__)


class Device:
    """Device data for ConfigurationFile (XCF) class."""

    interface: Interface
    part_number: Optional[str]
    product_code: Optional[int]
    revision_number: Optional[int]
    firmware_version: Optional[str]
    node_id: Optional[int] = None

    ELEMENT_NAME = "Device"
    INTERFACE_ATTR = "Interface"
    FW_VERSION_ATTR = "firmwareVersion"
    PRODUCT_CODE_ATTR = "ProductCode"
    PART_NUMBER_ATTR = "PartNumber"
    REVISION_NUMBER_ATTR = "RevisionNumber"
    NODE_ID_ATTR = "NodeID"

    INTERFACE_XCF_OPTIONS = {
        "CAN": Interface.CAN,
        "ECAT": Interface.ECAT,
        "EoE": Interface.EoE,
        "ETH": Interface.ETH,
    }

    def __init__(
        self,
        interface: Interface,
        part_number: Optional[str],
        product_code: Optional[int],
        revision_number: Optional[int],
        firmware_version: Optional[str],
        node_id: Optional[int] = None,
    ):
        if interface != Interface.CAN and node_id is not None:
            raise NotImplementedError("node_id field is only supported by CANopen devices")
        self.interface = interface
        self.part_number = part_number
        self.product_code = product_code
        self.revision_number = revision_number
        self.firmware_version = firmware_version
        self.node_id = node_id

        self.interface_value_to_str = {
            value: key for key, value in self.INTERFACE_XCF_OPTIONS.items()
        }
        self.interface_value_to_str[Interface.VIRTUAL] = "ETH"

    @classmethod
    def from_xcf(cls, element: ElementTree.Element) -> "Device":
        """Creates a Device instance from XML element.

        Returns:
            Device instance filled with XML element data
        """
        interface = cls.INTERFACE_XCF_OPTIONS[element.attrib[cls.INTERFACE_ATTR]]
        part_number = element.attrib.get(cls.PART_NUMBER_ATTR)
        product_code_raw = element.attrib.get(cls.PRODUCT_CODE_ATTR)
        product_code = int(product_code_raw) if product_code_raw else None
        revision_number_raw = element.attrib.get(cls.REVISION_NUMBER_ATTR)
        revision_number = int(revision_number_raw) if revision_number_raw else None
        firmware_version = element.attrib.get(cls.FW_VERSION_ATTR)
        node_id_raw = element.attrib.get(cls.NODE_ID_ATTR)
        node_id = int(node_id_raw) if node_id_raw else None
        return cls(interface, part_number, product_code, revision_number, firmware_version, node_id)

    def to_xcf(self) -> ElementTree.Element:
        """Creates an XML element with class data.

        Returns:
            XML element dilled with class data
        """
        register_xml = ElementTree.Element(self.ELEMENT_NAME)
        register_xml.set(self.INTERFACE_ATTR, self.interface_value_to_str[self.interface])
        if self.firmware_version is not None:
            register_xml.set(self.FW_VERSION_ATTR, self.firmware_version)
        if self.product_code is not None:
            register_xml.set(self.PRODUCT_CODE_ATTR, str(self.product_code))
        if self.part_number is not None:
            register_xml.set(self.PART_NUMBER_ATTR, self.part_number)
        if self.revision_number is not None:
            register_xml.set(self.REVISION_NUMBER_ATTR, str(self.revision_number))
        if self.node_id is not None:
            register_xml.set(self.NODE_ID_ATTR, str(self.node_id))
        return register_xml


class ConfigRegister:
    """Register class for ConfigurationFile (XCF) class."""

    ELEMENT_NAME = "Register"
    ACCESS_ATTR = "access"
    DTYPE_ATTR = "dtype"
    ID_ATTR = "id"
    SUBNODE_ATTR = "subnode"
    STORAGE_ATTR = "storage"

    def __init__(
        self,
        uid: str,
        subnode: int,
        dtype: RegDtype,
        access: RegAccess,
        storage: Union[float, int, str, bool],
    ):
        self.uid = uid
        self.subnode = subnode
        self.dtype = dtype
        self.access = access
        self.storage = storage

        self.access_value_to_str = {
            value: key for key, value in Dictionary.access_xdf_options.items()
        }
        self.dtype_value_to_str = {
            value: key for key, value in Dictionary.dtype_xdf_options.items()
        }

    @classmethod
    def from_xcf(cls, element: ElementTree.Element) -> "ConfigRegister":
        """Creates a register from register XML element.

        Returns:
            ConfigRegister filled with XML element data

        Raises:
            ValueError: wrong fields type
            KeyError: an attribute is missing
        """
        uid = element.attrib[cls.ID_ATTR]
        subnode = int(element.attrib[cls.SUBNODE_ATTR])
        dtype = Dictionary.dtype_xdf_options[element.attrib[cls.DTYPE_ATTR]]
        access = Dictionary.access_xdf_options[element.attrib[cls.ACCESS_ATTR]]
        storage: Union[float, int, str, bool]
        if dtype == RegDtype.FLOAT:
            storage = float(element.attrib[cls.STORAGE_ATTR])
        elif dtype in [
            RegDtype.S8,
            RegDtype.U8,
            RegDtype.S16,
            RegDtype.U16,
            RegDtype.S32,
            RegDtype.U32,
            RegDtype.S64,
            RegDtype.U64,
        ]:
            storage = int(element.attrib[cls.STORAGE_ATTR])
        elif dtype == RegDtype.STR:
            storage = element.attrib[cls.STORAGE_ATTR]
        elif dtype == RegDtype.BOOL:
            storage = bool(element.attrib[cls.STORAGE_ATTR])
        else:
            raise NotImplementedError
        return cls(uid, subnode, dtype, access, storage)

    @classmethod
    def from_register(
        cls, register: Register, value: Union[float, int, str, bool]
    ) -> "ConfigRegister":
        """Creates a ConfigRegister from a register, and it's value.

        Returns:
            ConfigRegister instance filled with register data

        Raises:
            ValueError: Register has no an identifier
        """
        if register.identifier is None:
            raise ValueError("register has not an identifier")
        return cls(register.identifier, register.subnode, register.dtype, register.access, value)

    def to_xcf(self) -> ElementTree.Element:
        """Creates a XMl element from class data.

        Returns:
            XML register element filled with class data
        """
        register_xml = ElementTree.Element(self.ELEMENT_NAME)
        register_xml.set(self.ACCESS_ATTR, self.access_value_to_str[self.access])
        register_xml.set(self.DTYPE_ATTR, self.dtype_value_to_str[self.dtype])
        register_xml.set(self.ID_ATTR, self.uid)
        register_xml.set(self.SUBNODE_ATTR, str(self.subnode))
        if isinstance(self.storage, float):
            register_xml.set(self.STORAGE_ATTR, str(np.float32(self.storage)))
        else:
            register_xml.set(self.STORAGE_ATTR, str(self.storage))
        return register_xml


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


class ConfigurationFile(XMLBase, ABC):
    """Configuration file (XCF) class.

    It can be generated from a XCF file or be exported to a XCF file.
    """

    _VERSION_REGEX = r"(\d+)\.*(\d*)"
    _MAJOR_VERSION_GROUP = 1
    _MINOR_VERSION_GROUP = 2
    _CHECK_FAIL_EXCEPTION = ILConfigurationFileParseError

    def __init__(self) -> None:
        self.major_version = 2
        self.minor_version = 1
        self.registers: list[ConfigRegister] = []
        self.device: Optional[Device] = None
        self.subnodes: set[int] = set()

    @classmethod
    def __read_version(cls, version_element: ElementTree.Element) -> tuple[int, int]:
        """Process Version element and set version.

        Args:
            version_element: Version element

        Returns:
            major and minor version

        Raises:
            ILConfigurationFileParseError: version is empty

        """
        if version_element.text is None:
            raise ILConfigurationFileParseError("Version is empty")
        version_str = version_element.text.strip()
        version_match = re.match(cls._VERSION_REGEX, version_str)
        if version_match is None:
            raise ILConfigurationFileParseError("Version has a wrong format")
        major_version = int(version_match.group(cls._MAJOR_VERSION_GROUP))
        if version_match.group(cls._MINOR_VERSION_GROUP):
            minor_version = int(version_match.group(cls._MINOR_VERSION_GROUP))
        else:
            minor_version = 0
        return major_version, minor_version

    @classmethod
    def from_xcf(cls, xcf_path: str) -> "ConfigurationFile":
        """Creates a XCF instance from a XCF file.

        Args:
            xcf_path: XCF file path

        Returns:
            XCF instance with XCF file data

        Raises:
            FileNotFoundError: xcf_path file not found
        """
        if not os.path.isfile(xcf_path):
            raise FileNotFoundError(f"Could not find {xcf_path}.")
        with open(xcf_path, encoding="utf-8") as xml_file:
            tree = ElementTree.parse(xml_file)
        root = tree.getroot()
        version = cls._find_and_check(root, "Header/Version")
        device_element = cls._find_and_check(root, "Body/Device")
        registers_element = cls._find_and_check(device_element, "Registers")
        register_element_list = cls._findall_and_check(registers_element, "Register")
        conifg_registers: list[ConfigRegister] = []
        subnodes_set = set()
        for reg in register_element_list:
            try:
                config_reg = ConfigRegister.from_xcf(reg)
                conifg_registers.append(config_reg)
                subnodes_set.add(config_reg.subnode)
            except (ValueError, KeyError) as e: # noqa: PERF203
                logger.warning(f"{reg}: {e}")
        config_device = Device.from_xcf(device_element)
        major_version, minor_version = cls.__read_version(version)
        xcf_instance = cls()
        xcf_instance.registers = conifg_registers
        xcf_instance.device = config_device
        xcf_instance.major_version = major_version
        xcf_instance.minor_version = minor_version
        xcf_instance.subnodes = subnodes_set
        return xcf_instance

    @classmethod
    def create_xcf(
        cls,
        interface: Interface,
        part_number: Optional[str],
        product_code: Optional[int],
        revision_number: Optional[int],
        firmware_version: Optional[str],
        node_id: Optional[int] = None,
    ) -> "ConfigurationFile":
        """Create an empty XCF with the device info.

        Args:
            interface: drive interface
            part_number: drive part number
            product_code: drive product code
            revision_number: drive firmware revision number
            firmware_version: drive firmware version
            node_id: drive node id. Only for CANopen drives

        Returns:
            creates a XCF instance
        """
        xcf_instance = cls()
        xcf_instance.device = Device(
            interface, part_number, product_code, revision_number, firmware_version, node_id
        )
        return xcf_instance

    def add_register(self, register: Register, value: Union[float, int, str, bool]) -> None:
        """Add register to the XCF class.

        Args:
            register: register that will be added to the XCF
            value: value that will be added to the register in te XCF

        """
        config_register = ConfigRegister.from_register(register, value)
        self.registers.append(config_register)
        self.subnodes.add(config_register.subnode)

    def to_xcf(self, xcf_path: str) -> None:
        """Save a file with the config file in the target path

        Args:
            xcf_path: config file target path

        """
        if self.device is None:
            raise TypeError("device is empty")
        if not self.registers:
            raise ValueError("registers is empty")
        tree = ElementTree.Element("IngeniaDictionary")
        header = ElementTree.SubElement(tree, "Header")
        body = ElementTree.SubElement(tree, "Body")
        version = ElementTree.SubElement(header, "Version")
        version.text = self.version
        device = self.device.to_xcf()
        registers = ElementTree.SubElement(device, "Registers")
        for register in self.registers:
            registers.append(register.to_xcf())
        body.append(device)
        dom = minidom.parseString(ElementTree.tostring(tree, encoding="utf-8"))
        with open(xcf_path, "wb") as f:
            f.write(dom.toprettyxml(indent="\t").encode())

    @property
    def version(self) -> str:
        """Version string"""
        if self.minor_version != 0:
            return f"{self.major_version}.{self.minor_version}"
        else:
            return f"{self.major_version}"
