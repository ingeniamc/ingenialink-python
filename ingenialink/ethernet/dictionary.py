from functools import cached_property
from typing import Optional
from xml.etree import ElementTree

import ingenialogger

from ingenialink.dictionary import DictionarySafetyModule, DictionaryV2, Interface
from ingenialink.enums.register import RegAccess, RegCyclicType, RegDtype
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.ethernet.register import EthernetRegister
from ingenialink.register import MonitoringV3

logger = ingenialogger.get_logger(__name__)


class EthernetDictionaryV2(DictionaryV2):
    """Contains all registers and information of a Ethernet dictionary.

    Args:
        dictionary_path: Path to the Ingenia dictionary.

    """

    interface = Interface.ETH

    @cached_property
    def _monitoring_disturbance_registers(self) -> list[EthernetRegister]:
        return [
            EthernetRegister(
                identifier="MON_DATA_VALUE",
                units="",
                subnode=0,
                address=0x00B2,
                pdo_access=RegCyclicType.CONFIG,
                dtype=RegDtype.BYTE_ARRAY_512,
                access=RegAccess.RO,
            ),
            EthernetRegister(
                identifier="DIST_DATA_VALUE",
                units="",
                subnode=0,
                address=0x00B4,
                pdo_access=RegCyclicType.CONFIG,
                dtype=RegDtype.BYTE_ARRAY_512,
                access=RegAccess.WO,
            ),
        ]

    @cached_property
    def _safety_registers(self) -> list[EthercatRegister]:
        return [
            EthercatRegister(
                identifier="FSOE_TOTAL_ERROR",
                idx=0x4193,
                subidx=0x00,
                dtype=RegDtype.U16,
                access=RegAccess.RW,
                subnode=0,
            ),
            EthercatRegister(
                identifier="MDP_CONFIGURED_MODULE_1",
                idx=0xF030,
                subidx=0x01,
                dtype=RegDtype.U32,
                access=RegAccess.RW,
                subnode=0,
            ),
            EthercatRegister(
                identifier="FSOE_SAFE_INPUTS_MAP",
                idx=0x46D2,
                subidx=0x00,
                dtype=RegDtype.U16,
                access=RegAccess.RW,
                subnode=0,
            ),
            EthercatRegister(
                identifier="FSOE_SS1_TIME_TO_STO_1",
                idx=0x6651,
                subidx=0x01,
                dtype=RegDtype.U16,
                access=RegAccess.RW,
                subnode=0,
            ),
        ]

    @cached_property
    def _safety_modules(self) -> list[DictionarySafetyModule]:
        def __module_ident(module_idx: int) -> int:
            if self.product_code is None:
                raise ValueError("Module ident cannot be calculated, product code missing.")
            return (self.product_code & 0x7F00000) + module_idx

        return [
            DictionarySafetyModule(
                uses_sra=False,
                module_ident=__module_ident(0),
                application_parameters=[
                    DictionarySafetyModule.ApplicationParameter(uid="FSOE_SAFE_INPUTS_MAP"),
                    DictionarySafetyModule.ApplicationParameter(uid="FSOE_SS1_TIME_TO_STO_1"),
                ],
            ),
            DictionarySafetyModule(
                uses_sra=True,
                module_ident=__module_ident(1),
                application_parameters=[
                    DictionarySafetyModule.ApplicationParameter(uid="FSOE_SAFE_INPUTS_MAP"),
                    DictionarySafetyModule.ApplicationParameter(uid="FSOE_SS1_TIME_TO_STO_1"),
                ],
            ),
        ]

    def _read_xdf_register(self, register: ElementTree.Element) -> Optional[EthernetRegister]:
        current_read_register = super()._read_xdf_register(register)
        if current_read_register is None:
            return None
        try:
            reg_address = int(register.attrib["address"], 16)

            monitoring: Optional[MonitoringV3] = None
            if current_read_register.pdo_access != RegCyclicType.CONFIG:
                monitoring = MonitoringV3(
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
            )

            return ethernet_register

        except KeyError as ke:
            logger.error(
                f"Register with ID {current_read_register.identifier} has not attribute {ke}"
            )
            return None
