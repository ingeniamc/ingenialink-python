from functools import cached_property
from typing import Optional
from xml.etree import ElementTree

import ingenialogger

from ingenialink.constants import (
    CANOPEN_ADDRESS_OFFSET,
    CANOPEN_SUBNODE_0_ADDRESS_OFFSET,
    MAP_ADDRESS_OFFSET,
)
from ingenialink.dictionary import DictionarySafetyModule, DictionaryV2, Interface
from ingenialink.enums.register import (
    RegAccess,
    RegAddressType,
    RegCyclicType,
    RegDtype,
)
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.register import MonDistV3

logger = ingenialogger.get_logger(__name__)


class EthercatDictionaryV2(DictionaryV2):
    """Contains all registers and information of a EtherCAT dictionary.

    Args:
        dictionary_path: Path to the Ingenia dictionary.

    """

    interface = Interface.ECAT

    @cached_property
    def _monitoring_disturbance_registers(self) -> list[EthercatRegister]:
        return [
            EthercatRegister(
                identifier="MON_DATA_VALUE",
                units="",
                subnode=0,
                idx=0x58B2,
                subidx=0x01,
                pdo_access=RegCyclicType.CONFIG,
                dtype=RegDtype.BYTE_ARRAY_512,
                access=RegAccess.RO,
            ),
            EthercatRegister(
                identifier="DIST_DATA_VALUE",
                units="",
                subnode=0,
                idx=0x58B4,
                subidx=0x01,
                pdo_access=RegCyclicType.CONFIG,
                dtype=RegDtype.BYTE_ARRAY_512,
                access=RegAccess.WO,
            ),
        ]

    @cached_property
    def _safety_registers(self) -> list[EthercatRegister]:
        return [
            EthercatRegister(
                identifier="FSOE_MANUF_SAFETY_ADDRESS",
                idx=0x4193,
                subidx=0x00,
                dtype=RegDtype.U16,
                access=RegAccess.RW,
                subnode=1,
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
                subnode=1,
            ),
            EthercatRegister(
                identifier="FSOE_SS1_TIME_TO_STO_1",
                idx=0x6651,
                subidx=0x01,
                dtype=RegDtype.U16,
                access=RegAccess.RW,
                subnode=1,
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

    @cached_property
    def __pdo_registers(self) -> list[EthercatRegister]:
        return [
            EthercatRegister(
                identifier="ETG_COMMS_RPDO_ASSIGN_TOTAL",
                units="",
                subnode=0,
                idx=0x1C12,
                subidx=0x00,
                dtype=RegDtype.S32,
                access=RegAccess.RW,
                address_type=RegAddressType.NVM_NONE,
            ),
            EthercatRegister(
                identifier="ETG_COMMS_RPDO_ASSIGN_1",
                units="",
                subnode=0,
                idx=0x1C12,
                subidx=0x01,
                dtype=RegDtype.S32,
                access=RegAccess.RW,
                address_type=RegAddressType.NVM_NONE,
            ),
            EthercatRegister(
                identifier="ETG_COMMS_RPDO_MAP1_TOTAL",
                units="",
                subnode=0,
                idx=0x1600,
                subidx=0x00,
                dtype=RegDtype.S32,
                access=RegAccess.RW,
                address_type=RegAddressType.NVM_NONE,
            ),
            EthercatRegister(
                identifier="ETG_COMMS_RPDO_MAP1_1",
                units="",
                subnode=0,
                idx=0x1600,
                subidx=0x01,
                dtype=RegDtype.STR,
                access=RegAccess.RW,
                address_type=RegAddressType.NVM_NONE,
            ),
            EthercatRegister(
                identifier="ETG_COMMS_TPDO_ASSIGN_TOTAL",
                units="",
                subnode=0,
                idx=0x1C13,
                subidx=0x00,
                dtype=RegDtype.S32,
                access=RegAccess.RW,
                address_type=RegAddressType.NVM_NONE,
            ),
            EthercatRegister(
                identifier="ETG_COMMS_TPDO_ASSIGN_1",
                units="",
                subnode=0,
                idx=0x1C13,
                subidx=0x01,
                dtype=RegDtype.S32,
                access=RegAccess.RW,
                address_type=RegAddressType.NVM_NONE,
            ),
            EthercatRegister(
                identifier="ETG_COMMS_TPDO_MAP1_TOTAL",
                units="",
                subnode=0,
                idx=0x1A00,
                subidx=0x00,
                dtype=RegDtype.S32,
                access=RegAccess.RW,
                address_type=RegAddressType.NVM_NONE,
            ),
            EthercatRegister(
                identifier="ETG_COMMS_TPDO_MAP1_1",
                units="",
                subnode=0,
                idx=0x1A00,
                subidx=0x01,
                dtype=RegDtype.STR,
                access=RegAccess.RW,
                address_type=RegAddressType.NVM_NONE,
            ),
        ]

    @staticmethod
    def __get_cia_offset(subnode: int) -> int:
        """Get the CiA offset for the register based on the subnode.

        Args:
            subnode: register subnode.

        Returns:
            The CiA offset for the register.
        """
        return (
            CANOPEN_SUBNODE_0_ADDRESS_OFFSET
            if subnode == 0
            else CANOPEN_ADDRESS_OFFSET + MAP_ADDRESS_OFFSET * (subnode - 1)
        )

    def _read_xdf_register(self, register: ElementTree.Element) -> Optional[EthercatRegister]:
        current_read_register = super()._read_xdf_register(register)
        if current_read_register is None:
            return None
        try:
            idx = int(register.attrib["address"], 16) + self.__get_cia_offset(
                current_read_register.subnode
            )
            subidx = 0x00

            monitoring: Optional[MonDistV3] = None
            if current_read_register.pdo_access != RegCyclicType.CONFIG:
                address = idx - (
                    CANOPEN_ADDRESS_OFFSET
                    + (MAP_ADDRESS_OFFSET * (current_read_register.subnode - 1))
                )
                monitoring = MonDistV3(
                    address=address,
                    subnode=current_read_register.subnode,
                    cyclic=current_read_register.pdo_access,
                )

            ethercat_register = EthercatRegister(
                idx,
                subidx,
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

            return ethercat_register

        except KeyError as ke:
            logger.error(
                f"Register with ID {current_read_register.identifier} has not attribute {ke}"
            )
            return None

    def _append_missing_registers(
        self,
    ) -> None:
        """Append missing registers to the dictionary.

        Mainly registers needed for Monitoring/Disturbance and PDOs.

        """
        super()._append_missing_registers()
        for register in self.__pdo_registers:
            if register.identifier is not None:
                self._registers[register.subnode][register.identifier] = register
