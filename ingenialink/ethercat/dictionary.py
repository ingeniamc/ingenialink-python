from collections.abc import Iterator
from functools import cached_property
from typing import Optional
from xml.etree import ElementTree

import ingenialogger

from ingenialink.canopen.dictionary import CanopenDictionary
from ingenialink.canopen.register import CanopenRegister
from ingenialink.constants import (
    CANOPEN_ADDRESS_OFFSET,
    CANOPEN_SUBNODE_0_ADDRESS_OFFSET,
    MAP_ADDRESS_OFFSET,
)
from ingenialink.dictionary import (
    CanOpenObject,
    CanOpenObjectType,
    DictionarySafetyModule,
    DictionaryV2,
    DictionaryV3,
    Interface,
)
from ingenialink.enums.register import (
    RegAccess,
    RegAddressType,
    RegCyclicType,
    RegDtype,
)
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.register import MonDistV3

logger = ingenialogger.get_logger(__name__)


class EthercatDictionary(CanopenDictionary):
    """Base class for EtherCAT dictionaries."""

    interface = Interface.ECAT


class EthercatDictionaryV2(EthercatDictionary, DictionaryV2):
    """Contains all registers and information of a EtherCAT dictionary.

    Args:
        dictionary_path: Path to the Ingenia dictionary.

    """

    @cached_property
    def _monitoring_disturbance_registers(self) -> list[EthercatRegister]:
        return [
            EthercatRegister(
                identifier="MON_DATA_VALUE",
                units="none",
                subnode=0,
                idx=0x58B2,
                subidx=0x01,
                pdo_access=RegCyclicType.CONFIG,
                dtype=RegDtype.BYTE_ARRAY_512,
                access=RegAccess.RO,
                labels={"en_US": "Monitoring data"},
                cat_id="MONITORING",
            ),
            EthercatRegister(
                identifier="DIST_DATA_VALUE",
                units="none",
                subnode=0,
                idx=0x58B4,
                subidx=0x01,
                pdo_access=RegCyclicType.CONFIG,
                dtype=RegDtype.BYTE_ARRAY_512,
                access=RegAccess.WO,
                labels={"en_US": "Disturbance data"},
                cat_id="MONITORING",
            ),
        ]

    @cached_property
    def _safety_registers(self) -> list[EthercatRegister]:
        return [
            EthercatRegister(
                identifier="FSOE_MANUF_SAFETY_ADDRESS",
                idx=0x4193,
                subidx=0x00,
                pdo_access=RegCyclicType.CONFIG,
                dtype=RegDtype.U16,
                access=RegAccess.RW,
                subnode=1,
                labels={"en_US": "Safety address"},
                cat_id="FSOE",
            ),
            EthercatRegister(
                identifier="MDP_CONFIGURED_MODULE_1",
                idx=0xF030,
                subidx=0x01,
                pdo_access=RegCyclicType.CONFIG,
                dtype=RegDtype.U32,
                access=RegAccess.RW,
                subnode=0,
                labels={"en_US": "Configured module ident of the module 1"},
                cat_id="MDP",
            ),
            EthercatRegister(
                identifier="FSOE_SAFE_INPUTS_MAP",
                idx=0x46D2,
                subidx=0x00,
                pdo_access=RegCyclicType.CONFIG,
                dtype=RegDtype.U16,
                access=RegAccess.RW,
                subnode=1,
                cat_id="FSOE",
                labels={"en_US": "Safe Inputs Map"},
            ),
            EthercatRegister(
                identifier="FSOE_SS1_TIME_TO_STO_1",
                idx=0x6651,
                subidx=0x01,
                pdo_access=RegCyclicType.CONFIG,
                dtype=RegDtype.U16,
                access=RegAccess.RW,
                subnode=0,
                labels={"en_US": "SS1 Time to STO"},
                cat_id="FSOE",
            ),
            EthercatRegister(
                identifier="FSOE_STO",
                idx=0x6640,
                subidx=0,
                dtype=RegDtype.BOOL,
                access=RegAccess.RO,
                pdo_access=RegCyclicType.SAFETY_INPUT_OUTPUT,
                subnode=1,
                cat_id="FSOE",
            ),
            EthercatRegister(
                identifier="FSOE_SS1_1",
                idx=0x6650,
                subidx=1,
                dtype=RegDtype.BOOL,
                access=RegAccess.RO,
                pdo_access=RegCyclicType.SAFETY_INPUT_OUTPUT,
                subnode=1,
                cat_id="FSOE",
            ),
            EthercatRegister(
                identifier="FSOE_SAFE_INPUTS_VALUE",
                idx=0x46D1,
                subidx=0,
                dtype=RegDtype.BOOL,
                access=RegAccess.RO,
                pdo_access=RegCyclicType.SAFETY_INPUT,
                subnode=1,
                cat_id="FSOE",
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

    def __create_pdo_map_assign(
        self, idx: int, base_uid: str, base_label: str, n_elements: int
    ) -> CanOpenObject:
        """Generate PDO assignment registers.

        Args:
            idx (int): Index of register.
            base_uid (str): Base unique identifier.
            base_label (str): Base label.
            n_elements (int): Number of elements of the pdo assign

        Returns:
            CanOpenObject: Object containing the registers for a pdo map assign.
        """
        return CanOpenObject(
            uid=base_uid,
            idx=idx,
            object_type=CanOpenObjectType.ARRAY,
            registers=list[CanopenRegister](
                [
                    # Total register
                    EthercatRegister(
                        identifier=f"{base_uid}_TOTAL",
                        units="cnt",
                        subnode=0,
                        idx=idx,
                        subidx=0x00,
                        pdo_access=RegCyclicType.CONFIG,
                        dtype=RegDtype.U8,
                        access=RegAccess.RW,
                        address_type=RegAddressType.NVM_NONE,
                        labels={"en_US": "SubIndex 000"},
                        cat_id="COMMUNICATIONS",
                    )
                ]
                + [
                    # Element registers
                    EthercatRegister(
                        identifier=f"{base_uid}_{i}",
                        units="none",
                        subnode=0,
                        idx=idx,
                        subidx=i,
                        pdo_access=RegCyclicType.CONFIG,
                        dtype=RegDtype.U16,
                        access=RegAccess.RW,
                        address_type=RegAddressType.NVM_NONE,
                        labels={"en_US": f"{base_label} Element {i}"},
                        cat_id="COMMUNICATIONS",
                    )
                    for i in range(1, n_elements + 1)
                ],
            ),
        )

    def __create_pdo_map(
        self,
        idx: int,
        base_uid: str,
        base_label: str,
        n_elements: int,
        read_only: bool = False,
        subnode: int = 0,
    ) -> CanOpenObject:
        """Generate PDO map registers.

        Args:
            idx: Index of register.
            base_uid: Base unique identifier.
            base_label: Base label.
            n_elements: Number of elements of the pdo map.
            read_only: If True, the PDO map is read-only (default is False).
            subnode: Subnode for the registers (default is 0).

        Returns:
            CanOpenObject: Object containing the registers for a pdo map.
        """
        return CanOpenObject(
            uid=base_uid,
            idx=idx,
            object_type=CanOpenObjectType.RECORD,
            registers=list[CanopenRegister](
                [
                    # Total register
                    EthercatRegister(
                        identifier=f"{base_uid}_TOTAL",
                        units="none",
                        subnode=subnode,
                        idx=idx,
                        subidx=0x00,
                        pdo_access=RegCyclicType.CONFIG,
                        dtype=RegDtype.U8,
                        access=RegAccess.RO if read_only else RegAccess.RW,
                        address_type=RegAddressType.NVM_NONE,
                        labels={"en_US": "SubIndex 000"},
                        cat_id="COMMUNICATIONS",
                    )
                ]
                + [
                    # Element registers
                    EthercatRegister(
                        identifier=f"{base_uid}_{i}",
                        units="none",
                        subnode=subnode,
                        idx=idx,
                        subidx=i,
                        pdo_access=RegCyclicType.CONFIG,
                        dtype=RegDtype.U32,
                        access=RegAccess.RO if read_only else RegAccess.RW,
                        address_type=RegAddressType.NVM_NONE,
                        labels={"en_US": f"{base_label} Element {i}"},
                        cat_id="COMMUNICATIONS",
                    )
                    for i in range(1, n_elements + 1)
                ]
            ),
        )

    def __create_pdo_objects(self) -> Iterator[CanOpenObject]:
        # RPDO Assignments
        yield self.__create_pdo_map_assign(
            idx=0x1C12,
            base_uid="ETG_COMMS_RPDO_ASSIGN",
            base_label="RxPDO assign",
            n_elements=3,
        )
        # RPDO Map 1
        yield self.__create_pdo_map(
            idx=0x1600,
            base_uid="ETG_COMMS_RPDO_MAP1",
            base_label="RxPDO Map 1",
            n_elements=15,
        )
        # RPDO Map 2
        yield self.__create_pdo_map(
            idx=0x1601,
            base_uid="ETG_COMMS_RPDO_MAP2",
            base_label="RxPDO Map 2",
            n_elements=15,
        )
        # RPDO Map 3
        yield self.__create_pdo_map(
            idx=0x1602,
            base_uid="ETG_COMMS_RPDO_MAP3",
            base_label="RxPDO Map 3",
            n_elements=15,
        )
        # TPDO Assignments
        yield self.__create_pdo_map_assign(
            idx=0x1C13,
            base_uid="ETG_COMMS_TPDO_ASSIGN",
            base_label="TxPDO assign",
            n_elements=3,
        )
        # TPDO Map
        yield self.__create_pdo_map(
            idx=0x1A00,
            base_uid="ETG_COMMS_TPDO_MAP1",
            base_label="TxPDO Map 1",
            n_elements=15,
        )
        # TPDO Map
        yield self.__create_pdo_map(
            idx=0x1A01,
            base_uid="ETG_COMMS_TPDO_MAP2",
            base_label="TxPDO Map 2",
            n_elements=15,
        )
        # TPDO Map
        yield self.__create_pdo_map(
            idx=0x1A02,
            base_uid="ETG_COMMS_TPDO_MAP3",
            base_label="TxPDO Map 3",
            n_elements=15,
        )

        if self.is_safe:
            # XDF V2 only supports phase I, where the pdo map is read-only
            yield self.__create_pdo_map(
                idx=0x1700,
                base_uid="ETG_COMMS_RPDO_MAP256",
                base_label="RxPDO Map 256",
                n_elements=16,
                read_only=True,
                subnode=1,
            )
            yield self.__create_pdo_map(
                idx=0x1B00,
                base_uid="ETG_COMMS_TPDO_MAP256",
                base_label="RxPDO Map 256",
                n_elements=16,
                read_only=True,
                subnode=1,
            )

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
        if self.part_number in ["DEN-S-NET-E", "EVS-S-NET-E"]:
            self.is_safe = True

        for obj in self.__create_pdo_objects():
            for register in obj.registers:
                self._add_register_list(register)
            subnode = obj.registers[0].subnode
            if subnode not in self.items:
                self.items[subnode] = {}
            self.items[subnode][obj.uid] = obj

        if self.is_safe:
            for safety_submodule in self._safety_modules:
                self.safety_modules[safety_submodule.module_ident] = safety_submodule
            for register in self._safety_registers:
                self._add_register_list(register)


class EthercatDictionaryV3(EthercatDictionary, DictionaryV3):
    """Contains all registers and information of a EtherCAT dictionary.

    Args:
        dictionary_path: Path to the Ingenia dictionary.

    """
