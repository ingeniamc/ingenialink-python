from typing import List, Dict, Optional, Union, Tuple

from ingenialink.dictionary import Dictionary
from ingenialink.canopen.register import CanopenRegister
from ingenialink.register import Register, REG_DTYPE, REG_ACCESS, REG_ADDRESS_TYPE

import ingenialogger
import xml.etree.ElementTree as ET

logger = ingenialogger.get_logger(__name__)


class CanopenDictionary(Dictionary):
    """Contains all registers and information of a CANopen dictionary.

    Args:
        dictionary_path (str): Path to the Ingenia dictionary.

    """

    def __init__(self, dictionary_path: str) -> None:
        super().__init__(dictionary_path)

    def _read_xdf_register(self, register: ET.Element) -> Optional[CanopenRegister]:
        current_read_register = super()._read_xdf_register(register)
        if current_read_register is None:
            return None
        try:
            aux_var = int(register.attrib["address"], 16)
            idx = aux_var >> 8
            subidx = aux_var & 0xFF

            canopen_register = CanopenRegister(
                current_read_register.identifier,
                current_read_register.units,
                current_read_register.cyclic,
                idx,
                subidx,
                current_read_register.dtype,
                current_read_register.access,
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

            return canopen_register

        except KeyError as ke:
            logger.error(
                f"Register with ID {current_read_register.identifier} has not attribute {ke}"
            )
            return None
