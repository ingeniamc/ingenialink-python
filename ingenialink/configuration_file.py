import os
import re
from abc import ABC
from typing import Optional, Union
from xml.dom import minidom
from xml.etree import ElementTree

import ingenialogger
import numpy as np

from ingenialink import RegAccess, RegDtype
from ingenialink.dictionary import ACCESS_XDF_OPTIONS, DTYPE_XDF_OPTIONS, Interface, XMLBase
from ingenialink.exceptions import ILConfigurationFileParseError
from ingenialink.register import Register

logger = ingenialogger.get_logger(__name__)

_INTERFACE_XCF_OPTIONS: dict[str, Interface] = {
    "CAN": Interface.CAN,
    "ECAT": Interface.ECAT,
    "EoE": Interface.EoE,
    "ETH": Interface.ETH,
}


class Device:
    """Device data for ConfigurationFile (XCF) class."""

    interface: Interface
    part_number: Optional[str]
    product_code: Optional[int]
    revision_number: Optional[int]
    firmware_version: Optional[str]
    node_id: Optional[int] = None

    _ELEMENT_NAME = "Device"
    __INTERFACE_ATTR = "Interface"
    __FW_VERSION_ATTR = "firmwareVersion"
    __PRODUCT_CODE_ATTR = "ProductCode"
    __PART_NUMBER_ATTR = "PartNumber"
    __REVISION_NUMBER_ATTR = "RevisionNumber"
    __NODE_ID_ATTR = "NodeID"

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

        self.__interface_value_to_str = {
            value: key for key, value in _INTERFACE_XCF_OPTIONS.items()
        }
        self.__interface_value_to_str[Interface.VIRTUAL] = "ETH"

    @classmethod
    def from_xcf(cls, element: ElementTree.Element) -> "Device":
        """Creates a Device instance from XML element.

        Returns:
            Device instance filled with XML element data.
        """
        interface = _INTERFACE_XCF_OPTIONS[element.attrib[cls.__INTERFACE_ATTR]]
        part_number = element.attrib.get(cls.__PART_NUMBER_ATTR)
        product_code_raw = element.attrib.get(cls.__PRODUCT_CODE_ATTR)
        product_code = int(product_code_raw) if product_code_raw else None
        revision_number_raw = element.attrib.get(cls.__REVISION_NUMBER_ATTR)
        revision_number = int(revision_number_raw) if revision_number_raw else None
        firmware_version = element.attrib.get(cls.__FW_VERSION_ATTR)
        node_id_raw = element.attrib.get(cls.__NODE_ID_ATTR)
        node_id = int(node_id_raw) if node_id_raw else None
        return cls(interface, part_number, product_code, revision_number, firmware_version, node_id)

    def to_xcf(self) -> ElementTree.Element:
        """Creates an XML element with class data.

        Returns:
            XML element filled with class data
        """
        register_xml = ElementTree.Element(self._ELEMENT_NAME)
        register_xml.set(self.__INTERFACE_ATTR, self.__interface_value_to_str[self.interface])
        if self.firmware_version is not None:
            register_xml.set(self.__FW_VERSION_ATTR, self.firmware_version)
        if self.product_code is not None:
            register_xml.set(self.__PRODUCT_CODE_ATTR, str(self.product_code))
        if self.part_number is not None:
            register_xml.set(self.__PART_NUMBER_ATTR, self.part_number)
        if self.revision_number is not None:
            register_xml.set(self.__REVISION_NUMBER_ATTR, str(self.revision_number))
        if self.node_id is not None:
            register_xml.set(self.__NODE_ID_ATTR, str(self.node_id))
        return register_xml


class ConfigRegister:
    """Register class for ConfigurationFile (XCF) class."""

    _ELEMENT_NAME = "Register"
    __ACCESS_ATTR = "access"
    __DTYPE_ATTR = "dtype"
    __ID_ATTR = "id"
    __SUBNODE_ATTR = "subnode"
    __STORAGE_ATTR = "storage"

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

        self.__access_value_to_str = {value: key for key, value in ACCESS_XDF_OPTIONS.items()}
        self.__dtype_value_to_str = {value: key for key, value in DTYPE_XDF_OPTIONS.items()}

    @classmethod
    def from_xcf(cls, element: ElementTree.Element) -> "ConfigRegister":
        """Creates a register from register XML element.

        Returns:
            ConfigRegister filled with XML element data
        """
        uid = element.attrib[cls.__ID_ATTR]
        subnode = int(element.attrib[cls.__SUBNODE_ATTR])
        dtype = DTYPE_XDF_OPTIONS[element.attrib[cls.__DTYPE_ATTR]]
        access = ACCESS_XDF_OPTIONS[element.attrib[cls.__ACCESS_ATTR]]
        storage: Union[float, int, str, bool]
        if dtype == RegDtype.FLOAT:
            storage = float(element.attrib[cls.__STORAGE_ATTR])
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
            storage = int(element.attrib[cls.__STORAGE_ATTR])
        elif dtype == RegDtype.STR:
            storage = element.attrib[cls.__STORAGE_ATTR]
        elif dtype == RegDtype.BOOL:
            storage = bool(element.attrib[cls.__STORAGE_ATTR])
        else:
            raise NotImplementedError
        return cls(uid, subnode, dtype, access, storage)

    @classmethod
    def from_register(
        cls, register: Register, value: Union[float, int, str, bool]
    ) -> "ConfigRegister":
        """Creates a ConfigRegister from a register, and its value.

        Returns:
            ConfigRegister instance filled with register data

        Raises:
            ValueError: Register has no an identifier
        """
        if register.identifier is None:
            raise ValueError("register has not an identifier")
        return cls(register.identifier, register.subnode, register.dtype, register.access, value)

    def to_xcf(self) -> ElementTree.Element:
        """Creates a XML element from class data.

        Returns:
            XML register element filled with class data
        """
        register_xml = ElementTree.Element(self._ELEMENT_NAME)
        register_xml.set(self.__ACCESS_ATTR, self.__access_value_to_str[self.access])
        register_xml.set(self.__DTYPE_ATTR, self.__dtype_value_to_str[self.dtype])
        register_xml.set(self.__ID_ATTR, self.uid)
        register_xml.set(self.__SUBNODE_ATTR, str(self.subnode))
        if isinstance(self.storage, float):
            register_xml.set(self.__STORAGE_ATTR, str(np.float32(self.storage)))
        else:
            register_xml.set(self.__STORAGE_ATTR, str(self.storage))
        return register_xml


class ConfigurationFile(XMLBase, ABC):
    """Configuration file (XCF) class.

    It can be generated from a XCF file or be exported to a XCF file.
    """

    _VERSION_REGEX = r"(\d+)\.*(\d*)"
    _MAJOR_VERSION_GROUP = 1
    _MINOR_VERSION_GROUP = 2
    _CHECK_FAIL_EXCEPTION = ILConfigurationFileParseError

    __ROOT_ELEMENT = "IngeniaDictionary"
    __HEADER_ELEMENT = "Header"
    __VERSION_ELEMENT = "Version"
    __BODY_ELEMENT = "Body"
    __REGISTERS_ELEMENT = "Registers"

    _SUPPORTED_MAJOR_VERSION = 2

    def __init__(self, device: Device) -> None:
        self.major_version = self._SUPPORTED_MAJOR_VERSION
        self.minor_version = 1
        self.__registers: list[ConfigRegister] = []
        self.__device: Device = device
        self.__subnodes: set[int] = set()

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
    def load_from_xcf(cls, xcf_path: str) -> "ConfigurationFile":
        """Creates a XCF instance from a XCF file.

        Args:
            xcf_path: XCF file path

        Returns:
            XCF instance with XCF file data

        Raises:
            FileNotFoundError: xcf_path file not found
            NotImplementedError: Configuration file version not supported
        """
        if not os.path.isfile(xcf_path):
            raise FileNotFoundError(f"Could not find {xcf_path}.")
        with open(xcf_path, encoding="utf-8") as xml_file:
            tree = ElementTree.parse(xml_file)
        root = tree.getroot()
        header = cls._find_and_check(root, cls.__HEADER_ELEMENT)
        version = cls._find_and_check(header, cls.__VERSION_ELEMENT)
        major_version, minor_version = cls.__read_version(version)
        if major_version != cls._SUPPORTED_MAJOR_VERSION:
            raise NotImplementedError(
                f"Configuration file not supported: "
                f"Supported version: {cls._SUPPORTED_MAJOR_VERSION}, "
                f"File version: {major_version}"
            )
        body = cls._find_and_check(root, cls.__BODY_ELEMENT)
        device_element = cls._find_and_check(body, Device._ELEMENT_NAME)
        registers_element = cls._find_and_check(device_element, cls.__REGISTERS_ELEMENT)
        register_element_list = cls._findall_and_check(
            registers_element, ConfigRegister._ELEMENT_NAME
        )
        config_device = Device.from_xcf(device_element)
        xcf_instance = cls(config_device)
        for reg in register_element_list:
            try:
                xcf_instance.add_config_register(ConfigRegister.from_xcf(reg))
            except (ValueError, KeyError) as e:  # noqa: PERF203
                logger.warning(f"{reg}: {e}")
        xcf_instance.major_version = major_version
        xcf_instance.minor_version = minor_version
        return xcf_instance

    @classmethod
    def create_empty_configuration(
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
        device = Device(
            interface, part_number, product_code, revision_number, firmware_version, node_id
        )
        xcf_instance = cls(device)
        return xcf_instance

    def add_register(self, register: Register, value: Union[float, int, str, bool]) -> None:
        """Add register to the XCF class.

        Args:
            register: register that will be added to the XCF
            value: value that will be added to the register in te XCF

        """
        config_register = ConfigRegister.from_register(register, value)
        self.add_config_register(config_register)

    def add_config_register(self, config_register: ConfigRegister) -> None:
        """Add ConfigRegister to the XCF class.

        Args:
            config_register: register that will be added to the XCF
        """
        self.__registers.append(config_register)
        self.__subnodes.add(config_register.subnode)

    def save_to_xcf(self, xcf_path: str) -> None:
        """Save a file with the config file in the target path.

        Args:
            xcf_path: config file target path

        Raises:
            ValueError: the configuration has no registers

        """
        if not self.registers:
            raise ValueError("registers is empty")
        tree = ElementTree.Element(self.__ROOT_ELEMENT)
        header = ElementTree.SubElement(tree, self.__HEADER_ELEMENT)
        body = ElementTree.SubElement(tree, self.__BODY_ELEMENT)
        version = ElementTree.SubElement(header, self.__VERSION_ELEMENT)
        version.text = self.version
        device = self.device.to_xcf()
        registers_element = ElementTree.SubElement(device, self.__REGISTERS_ELEMENT)
        for register in self.registers:
            registers_element.append(register.to_xcf())
        body.append(device)
        dom = minidom.parseString(ElementTree.tostring(tree, encoding="utf-8"))
        with open(xcf_path, "wb") as f:
            f.write(dom.toprettyxml(indent="\t").encode())

    @property
    def version(self) -> str:
        """Version string."""
        if self.minor_version != 0:
            return f"{self.major_version}.{self.minor_version}"
        else:
            return f"{self.major_version}"

    @property
    def device(self) -> Device:
        """Configuration file device."""
        return self.__device

    @property
    def registers(self) -> list[ConfigRegister]:
        """Configuration file registers."""
        return self.__registers

    def contains_node(self, subnode: int) -> bool:
        """Check of configuration file contains register of the target subnode.

        Args:
            subnode: target subnode number

        Returns:
            True if contains target subnode registers, else False
        """
        return subnode in self.__subnodes
