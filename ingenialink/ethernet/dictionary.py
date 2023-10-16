from typing import Optional, Dict, List

from ingenialink.dictionary import Dictionary
from ingenialink.ethernet.register import EthernetRegister

import ingenialogger
import xml.etree.ElementTree as ET

logger = ingenialogger.get_logger(__name__)


class EthernetDictionary(Dictionary):
    """Contains all registers and information of a Ethernet dictionary.

    Args:
        dictionary_path (str): Path to the Ingenia dictionary.

    """

    def __init__(self, dictionary_path: str) -> None:
        self._registers: List[Dict[str, EthernetRegister]] = []  # type: ignore [assignment]
        super().__init__(dictionary_path)

    def _read_xdf_register(self, register: ET.Element) -> Optional[EthernetRegister]:
        current_read_register = super()._read_xdf_register(register)
        if current_read_register is None:
            return None
        try:
            address = int(register.attrib["address"], 16)

            ethernet_register = EthernetRegister(
                address,
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

    def registers(self, subnode: int) -> Dict[str, EthernetRegister]:  # type: ignore [override]
        """Gets the register dictionary to the targeted subnode.

        Args:
            subnode (int): Identifier for the subnode.

        Returns:
            dict: Dictionary of all the registers for a subnode.

        """
        return self._registers[subnode]
