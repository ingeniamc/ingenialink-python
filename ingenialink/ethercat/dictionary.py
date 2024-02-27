from typing import Optional
import xml.etree.ElementTree as ET

import ingenialogger

from ingenialink.dictionary import DictionaryV2
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.constants import (
    CANOPEN_ADDRESS_OFFSET,
    CANOPEN_SUBNODE_0_ADDRESS_OFFSET,
    MAP_ADDRESS_OFFSET,
)

logger = ingenialogger.get_logger(__name__)


class EthercatDictionary(DictionaryV2):
    """Contains all registers and information of a EtherCAT dictionary.

    Args:
        dictionary_path: Path to the Ingenia dictionary.

    """

    @staticmethod
    def __get_cia_offset(subnode: int) -> int:
        """Get the CiA offset for the register based on the subnode.

        Args:
            subnode: register subnode.

        Returs:
            The CiA offset for the register.

        """
        return (
            CANOPEN_SUBNODE_0_ADDRESS_OFFSET
            if subnode == 0
            else CANOPEN_ADDRESS_OFFSET + MAP_ADDRESS_OFFSET * (subnode - 1)
        )

    def _read_xdf_register(self, register: ET.Element) -> Optional[EthercatRegister]:
        current_read_register = super()._read_xdf_register(register)
        if current_read_register is None:
            return None
        try:
            idx = int(register.attrib["address"], 16) + self.__get_cia_offset(
                current_read_register.subnode
            )
            subidx = 0x00

            ethercat_register = EthercatRegister(
                idx,
                subidx,
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

            return ethercat_register

        except KeyError as ke:
            logger.error(
                f"Register with ID {current_read_register.identifier} has not attribute {ke}"
            )
            return None
