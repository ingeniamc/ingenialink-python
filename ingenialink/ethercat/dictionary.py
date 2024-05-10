import xml.etree.ElementTree as ET
from typing import List, Optional

import ingenialogger

from ingenialink.constants import (
    CANOPEN_ADDRESS_OFFSET,
    CANOPEN_SUBNODE_0_ADDRESS_OFFSET,
    MAP_ADDRESS_OFFSET,
)
from ingenialink.dictionary import DictionaryV2, Interface
from ingenialink.ethercat.register import (
    EthercatRegister,
)
from ingenialink.register import REG_ACCESS, REG_ADDRESS_TYPE, REG_DTYPE, RegCyclicType

logger = ingenialogger.get_logger(__name__)


class EthercatDictionaryV2(DictionaryV2):
    """Contains all registers and information of a EtherCAT dictionary.

    Args:
        dictionary_path: Path to the Ingenia dictionary.

    """

    MONITORING_DISTURBANCE_REGISTERS: List[EthercatRegister] = [
        EthercatRegister(
            identifier="MONITORING_DATA",
            units="",
            subnode=0,
            idx=0x58B2,
            subidx=0x01,
            cyclic=RegCyclicType.CONFIG,
            dtype=REG_DTYPE.BYTE_ARRAY_512,
            access=REG_ACCESS.RO,
        ),
        EthercatRegister(
            identifier="DISTURBANCE_DATA",
            units="",
            subnode=0,
            idx=0x58B4,
            subidx=0x01,
            cyclic=RegCyclicType.CONFIG,
            dtype=REG_DTYPE.BYTE_ARRAY_512,
            access=REG_ACCESS.WO,
        ),
    ]

    PDO_REGISTERS: List[EthercatRegister] = [
        EthercatRegister(
            identifier="RPDO_ASSIGN_REGISTER_SUB_IDX_0",
            units="",
            subnode=0,
            idx=0x1C12,
            subidx=0x00,
            dtype=REG_DTYPE.S32,
            access=REG_ACCESS.RW,
            address_type=REG_ADDRESS_TYPE.NVM_NONE,
        ),
        EthercatRegister(
            identifier="RPDO_ASSIGN_REGISTER_SUB_IDX_1",
            units="",
            subnode=0,
            idx=0x1C12,
            subidx=0x01,
            dtype=REG_DTYPE.S32,
            access=REG_ACCESS.RW,
            address_type=REG_ADDRESS_TYPE.NVM_NONE,
        ),
        EthercatRegister(
            identifier="RPDO_MAP_REGISTER_SUB_IDX_0",
            units="",
            subnode=0,
            idx=0x1600,
            subidx=0x00,
            dtype=REG_DTYPE.S32,
            access=REG_ACCESS.RW,
            address_type=REG_ADDRESS_TYPE.NVM_NONE,
        ),
        EthercatRegister(
            identifier="RPDO_MAP_REGISTER_SUB_IDX_1",
            units="",
            subnode=0,
            idx=0x1600,
            subidx=0x01,
            dtype=REG_DTYPE.STR,
            access=REG_ACCESS.RW,
            address_type=REG_ADDRESS_TYPE.NVM_NONE,
        ),
        EthercatRegister(
            identifier="TPDO_ASSIGN_REGISTER_SUB_IDX_0",
            units="",
            subnode=0,
            idx=0x1C13,
            subidx=0x00,
            dtype=REG_DTYPE.S32,
            access=REG_ACCESS.RW,
            address_type=REG_ADDRESS_TYPE.NVM_NONE,
        ),
        EthercatRegister(
            identifier="TPDO_ASSIGN_REGISTER_SUB_IDX_1",
            units="",
            subnode=0,
            idx=0x1C13,
            subidx=0x01,
            dtype=REG_DTYPE.S32,
            access=REG_ACCESS.RW,
            address_type=REG_ADDRESS_TYPE.NVM_NONE,
        ),
        EthercatRegister(
            identifier="TPDO_MAP_REGISTER_SUB_IDX_0",
            units="",
            subnode=0,
            idx=0x1A00,
            subidx=0x00,
            dtype=REG_DTYPE.S32,
            access=REG_ACCESS.RW,
            address_type=REG_ADDRESS_TYPE.NVM_NONE,
        ),
        EthercatRegister(
            identifier="TPDO_MAP_REGISTER_SUB_IDX_1",
            units="",
            subnode=0,
            idx=0x1A00,
            subidx=0x01,
            dtype=REG_DTYPE.STR,
            access=REG_ACCESS.RW,
            address_type=REG_ADDRESS_TYPE.NVM_NONE,
        ),
    ]

    def __init__(self, dictionary_path: str):
        super().__init__(dictionary_path, Interface.ECAT)

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

    def _append_missing_registers(
        self,
    ) -> None:
        """Append missing registers to the dictionary.

        Mainly registers needed for Monitoring/Disturbance and PDOs.

        """
        super()._append_missing_registers()
        for register in self.PDO_REGISTERS:
            if register.identifier is not None:
                self._registers[register.subnode][register.identifier] = register
