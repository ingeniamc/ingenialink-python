from functools import cached_property
from typing import Optional
from xml.etree import ElementTree

import ingenialogger

from ingenialink.canopen.register import CanopenRegister
from ingenialink.dictionary import DictionarySafetyModule, DictionaryV2, Interface
from ingenialink.enums.register import RegAccess, RegCyclicType, RegDtype

logger = ingenialogger.get_logger(__name__)


class CanopenDictionaryV2(DictionaryV2):
    """Contains all registers and information of a CANopen dictionary.

    Args:
        dictionary_path: Path to the Ingenia dictionary.

    """

    interface = Interface.CAN

    @cached_property
    def _monitoring_disturbance_registers(self) -> list[CanopenRegister]:
        return [
            CanopenRegister(
                identifier="MON_DATA_VALUE",
                idx=0x58B2,
                subidx=0x00,
                cyclic=RegCyclicType.CONFIG,
                dtype=RegDtype.BYTE_ARRAY_512,
                access=RegAccess.RO,
                subnode=0,
            ),
            CanopenRegister(
                identifier="DIST_DATA_VALUE",
                idx=0x58B4,
                subidx=0x00,
                cyclic=RegCyclicType.CONFIG,
                dtype=RegDtype.BYTE_ARRAY_512,
                access=RegAccess.WO,
                subnode=0,
            ),
        ]

    @cached_property
    def _safety_modules(self) -> list[DictionarySafetyModule]:
        raise NotImplementedError("Safety modules are not implemented for this device.")

    def _read_xdf_register(self, register: ElementTree.Element) -> Optional[CanopenRegister]:
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
                bitfields=current_read_register.bitfields,
            )

            return canopen_register

        except KeyError as ke:
            logger.error(
                f"Register with ID {current_read_register.identifier} has not attribute {ke}"
            )
            return None
