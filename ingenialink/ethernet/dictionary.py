from functools import cached_property
from typing import Optional
from xml.etree import ElementTree

import ingenialogger

from ingenialink.dictionary import (
    Dictionary,
    DictionarySafetyModule,
    DictionaryV2,
    DictionaryV3,
    Interface,
)
from ingenialink.enums.register import RegAccess, RegCyclicType, RegDtype
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.ethernet.register import EthernetRegister
from ingenialink.register import MonDistV3

logger = ingenialogger.get_logger(__name__)


class EthernetDictionary(Dictionary):
    """Base class for Ethernet dictionaries."""

    interface = Interface.ETH


class EoEDictionary(Dictionary):
    """Base class for EoE dictionaries."""

    interface = Interface.EoE


class EthernetDictionaryV2(EthernetDictionary, DictionaryV2):
    """Contains all registers and information of a Ethernet dictionary.

    Args:
        dictionary_path: Path to the Ingenia dictionary.

    """

    @cached_property
    def _monitoring_disturbance_registers(self) -> list[EthernetRegister]:
        return [
            EthernetRegister(
                identifier="MON_DATA_VALUE",
                units="none",
                subnode=0,
                address=0x00B2,
                pdo_access=RegCyclicType.CONFIG,
                dtype=RegDtype.BYTE_ARRAY_512,
                access=RegAccess.RO,
                labels={"en_US": "Monitoring data"},
                cat_id="MONITORING",
            ),
            EthernetRegister(
                identifier="DIST_DATA_VALUE",
                units="none",
                subnode=0,
                address=0x00B4,
                pdo_access=RegCyclicType.CONFIG,
                dtype=RegDtype.BYTE_ARRAY_512,
                access=RegAccess.WO,
                labels={"en_US": "Disturbance data"},
                cat_id="MONITORING",
            ),
        ]

    @property
    def _safety_registers(self) -> list[EthercatRegister]:
        raise NotImplementedError("Safety registers are not implemented for this device.")

    @property
    def _safety_modules(self) -> list[DictionarySafetyModule]:
        raise NotImplementedError("Safety modules are not implemented for this device.")

    def _read_xdf_register(self, register: ElementTree.Element) -> Optional[EthernetRegister]:
        current_read_register = super()._read_xdf_register(register)
        if current_read_register is None:
            return None
        try:
            reg_address = int(register.attrib["address"], 16)

            monitoring: Optional[MonDistV3] = None
            if current_read_register.pdo_access != RegCyclicType.CONFIG:
                monitoring = MonDistV3(
                    address=reg_address,
                    subnode=current_read_register.subnode,
                    cyclic=current_read_register.pdo_access,
                )

            ethernet_register = EthernetRegister(
                reg_address,
                current_read_register.dtype,
                current_read_register.access,
                identifier=current_read_register.identifier,
                units=current_read_register.units,
                pdo_access=current_read_register.pdo_access,
                phy=current_read_register.phy,
                subnode=current_read_register.subnode,
                storage=current_read_register.storage,
                reg_range=current_read_register.range,
                labels=current_read_register.labels,
                enums=current_read_register.enums,
                cat_id=current_read_register.cat_id,
                scat_id=current_read_register.scat_id,
                internal_use=current_read_register.internal_use,
                address_type=current_read_register.address_type,
                bitfields=current_read_register.bitfields,
                monitoring=monitoring,
                description=current_read_register.description,
            )

            return ethernet_register

        except KeyError as ke:
            logger.error(
                f"Register with ID {current_read_register.identifier} has not attribute {ke}"
            )
            return None


class EthernetDictionaryV3(EthernetDictionary, DictionaryV3):
    """Contains all registers and information of a Ethernet dictionary.

    Args:
        dictionary_path: Path to the Ingenia dictionary.

    """


class EoEDictionaryV3(EoEDictionary, DictionaryV3):
    """Contains all registers and information of a EoE dictionary.

    Args:
        dictionary_path: Path to the Ingenia dictionary.

    """
