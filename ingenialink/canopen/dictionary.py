from functools import cached_property
from typing import Any, Optional, cast
from xml.etree import ElementTree

import ingenialogger

from ingenialink.canopen.register import CanopenRegister
from ingenialink.constants import (
    CANOPEN_ADDRESS_OFFSET,
    MAP_ADDRESS_OFFSET,
)
from ingenialink.dictionary import (
    CanOpenObject,
    Dictionary,
    DictionarySafetyModule,
    DictionaryV2,
    DictionaryV3,
    Interface,
)
from ingenialink.enums.register import RegAccess, RegCyclicType, RegDtype
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.register import MonDistV3

logger = ingenialogger.get_logger(__name__)


class CanopenDictionary(Dictionary):
    """Base class for CANopen dictionaries."""

    interface = Interface.CAN

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.__idx_subindex_map: dict[int, dict[int, CanopenRegister]] = {
            # Idx -> {subindex -> register}
        }
        self.__idx_map: dict[int, CanOpenObject] = {
            # Idx -> object
        }

        for objs in self.items.values():
            for obj in objs.values():
                index = obj.idx
                self.__idx_map[index] = obj

        for register in self.all_registers():
            register = cast("CanopenRegister", register)
            index = register.idx
            subindex = register.subidx
            if index not in self.__idx_subindex_map:
                self.__idx_subindex_map[index] = {subindex: register}
            else:
                self.__idx_subindex_map[index][subindex] = register

    def get_register_by_index_subindex(self, index: int, subindex: int) -> CanopenRegister:
        """Get a register by its index and subindex.

        Args:
            index: The index of the register.
            subindex: The subindex of the register.

        Returns:
            CanopenRegister: The register with the given index and subindex.
        """
        return self.__idx_subindex_map[index][subindex]

    def get_object_by_index(self, index: int) -> CanOpenObject:
        """Get an object by its index.

        Args:
            index: The index of the object.

        Returns:
            CanOpenObject: The object with the given index.
        """
        return self.__idx_map[index]


class CanopenDictionaryV2(CanopenDictionary, DictionaryV2):
    """Contains all registers and information of a CANopen dictionary.

    Args:
        dictionary_path: Path to the Ingenia dictionary.

    """

    @cached_property
    def _monitoring_disturbance_registers(self) -> list[CanopenRegister]:
        return [
            CanopenRegister(
                identifier="MON_DATA_VALUE",
                units="none",
                idx=0x58B2,
                subidx=0x00,
                pdo_access=RegCyclicType.CONFIG,
                dtype=RegDtype.BYTE_ARRAY_512,
                access=RegAccess.RO,
                subnode=0,
                labels={"en_US": "Monitoring data"},
                cat_id="MONITORING",
            ),
            CanopenRegister(
                identifier="DIST_DATA_VALUE",
                units="none",
                idx=0x58B4,
                subidx=0x00,
                pdo_access=RegCyclicType.CONFIG,
                dtype=RegDtype.BYTE_ARRAY_512,
                access=RegAccess.WO,
                subnode=0,
                labels={"en_US": "Disturbance data"},
                cat_id="MONITORING",
            ),
        ]

    @cached_property
    def _safety_registers(self) -> list[EthercatRegister]:
        raise NotImplementedError("Safety registers are not implemented for this device.")

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

            canopen_register = CanopenRegister(
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

            return canopen_register

        except KeyError as ke:
            logger.error(
                f"Register with ID {current_read_register.identifier} has not attribute {ke}"
            )
            return None


class CanopenDictionaryV3(CanopenDictionary, DictionaryV3):
    """Contains all registers and information of a CANopen dictionary.

    Args:
        dictionary_path: Path to the Ingenia dictionary.

    """
