import xml.etree.ElementTree as ET
from typing import List, Optional

import ingenialogger

from ingenialink.dictionary import DictionaryV2, Interface
from ingenialink.ethernet.register import REG_ACCESS, REG_DTYPE, EthernetRegister, RegCyclicType

logger = ingenialogger.get_logger(__name__)


class EthernetDictionaryV2(DictionaryV2):
    """Contains all registers and information of a Ethernet dictionary.

    Args:
        dictionary_path: Path to the Ingenia dictionary.

    """

    MONITORING_DISTURBANCE_REGISTERS: List[EthernetRegister] = [
        EthernetRegister(
            identifier="MON_DATA_VALUE",
            units="",
            subnode=0,
            address=0x00B2,
            cyclic=RegCyclicType.CONFIG,
            dtype=REG_DTYPE.BYTE_ARRAY_512,
            access=REG_ACCESS.RO,
        ),
        EthernetRegister(
            identifier="DIST_DATA_VALUE",
            units="",
            subnode=0,
            address=0x00B4,
            cyclic=RegCyclicType.CONFIG,
            dtype=REG_DTYPE.BYTE_ARRAY_512,
            access=REG_ACCESS.WO,
        ),
    ]

    def __init__(self, dictionary_path: str) -> None:
        super().__init__(dictionary_path, Interface.ETH)

    def _read_xdf_register(self, register: ET.Element) -> Optional[EthernetRegister]:
        current_read_register = super()._read_xdf_register(register)
        if current_read_register is None:
            return None
        try:
            reg_address = int(register.attrib["address"], 16)

            ethernet_register = EthernetRegister(
                reg_address,
                current_read_register.dtype,
                current_read_register.access,
                identifier=current_read_register.identifier,
                units=current_read_register.units,
                cyclic=current_read_register.cyclic,
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
            )

            return ethernet_register

        except KeyError as ke:
            logger.error(
                f"Register with ID {current_read_register.identifier} has not attribute {ke}"
            )
            return None
