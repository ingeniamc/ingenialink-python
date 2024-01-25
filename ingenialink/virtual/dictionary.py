import xml.etree.ElementTree as ET
from typing import Optional

import ingenialogger

from ingenialink.ethernet.dictionary import EthernetDictionary
from ingenialink.ethernet.register import EthernetRegister

logger = ingenialogger.get_logger(__name__)


class VirtualDictionary(EthernetDictionary):
    """Contains all registers and information of a dictionary compatible with the virtual drive.

    It adapts a canopen dictionary to work in the ethernet communication used for the virtual drive.

    Args:
        dictionary_path: Path to the Ingenia dictionary.

    """

    def _read_xdf_register(self, register: ET.Element) -> Optional[EthernetRegister]:
        current_read_register = super()._read_xdf_register(register)

        if current_read_register is None:
            return None

        if self.interface == "CAN" and (
            register.attrib["cat_id"] == "CIA402" or register.attrib["id"].startswith("CIA402_")
        ):
            return None

        try:
            if self.interface == "CAN":
                reg_address = int(register.attrib["address"][:6], 16)
                reg_address = reg_address - 0x2000
            else:
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
