from typing import Optional, List

from ingenialink.dictionary import DictionaryV2, Interface
from ingenialink.canopen.register import CanopenRegister, REG_DTYPE, REG_ACCESS, REG_ADDRESS_TYPE

import ingenialogger
import xml.etree.ElementTree as ET

logger = ingenialogger.get_logger(__name__)


class CanopenDictionaryV2(DictionaryV2):
    """Contains all registers and information of a CANopen dictionary.

    Args:
        dictionary_path: Path to the Ingenia dictionary.

    """

    MONITORING_DISTURBANCE_REGISTERS: List[CanopenRegister] = [
        CanopenRegister(
            identifier="MONITORING_DATA",
            idx=0x58B2,
            subidx=0x00,
            cyclic="CONFIG",
            dtype=REG_DTYPE.U16,
            access=REG_ACCESS.RO,
            subnode=0,
            address_type=REG_ADDRESS_TYPE.NVM_NONE,
        ),
        CanopenRegister(
            identifier="DISTURBANCE_DATA",
            idx=0x58B4,
            subidx=0x00,
            cyclic="CONFIG",
            dtype=REG_DTYPE.U16,
            access=REG_ACCESS.RW,
            subnode=0,
            address_type=REG_ADDRESS_TYPE.NVM_NONE,
        ),
    ]

    def __init__(self, dictionary_path: str):
        super().__init__(dictionary_path, Interface.CAN)

    def _read_xdf_register(self, register: ET.Element) -> Optional[CanopenRegister]:
        current_read_register = super()._read_xdf_register(register)
        if current_read_register is None:
            return None
        try:
            aux_var = int(register.attrib["address"], 16)
            idx = aux_var >> 8
            subidx = aux_var & 0xFF

            canopen_register = CanopenRegister(
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

            return canopen_register

        except KeyError as ke:
            logger.error(
                f"Register with ID {current_read_register.identifier} has not attribute {ke}"
            )
            return None
