from enum import Enum, auto

from dataclasses import dataclass, field
from typing import List, Callable

from ingenialink.ethercat.register import EthercatRegister
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.ethercat.dictionary import EthercatDictionary
from ingenialink.utils._utils import dtype_value
from ingenialink.register import REG_DTYPE, REG_ACCESS


class PDOType(Enum):
    TPDO = auto()
    RDPO = auto()


@dataclass
class PDOMapItem:
    register: EthercatRegister
    callback: Callable


@dataclass
class PDOMap:
    dictionary: EthercatDictionary
    rpdo_registers: List[PDOMapItem] = field(default_factory=list)
    tpdo_registers: List[PDOMapItem] = field(default_factory=list)

    def add_register(self, register: str, callback: Callable, pdo_type: PDOType, axis=1) -> None:
        reg = self.dictionary.registers(axis)[register]
        pdo_map_item = PDOMapItem(register=reg, callback=callback)
        if pdo_type == PDOType.RDPO:
            self.rpdo_registers.append(pdo_map_item)
        else:
            self.tpdo_registers.append(pdo_map_item)


class PDOMapper:
    RPDO_ASSIGN_REGISTER_SUB_IDX_0 = EthercatRegister(
        identifier="RPDO_ASSIGN_REGISTER",
        units="",
        subnode=0,
        idx=0x1C12,
        subidx=0x00,
        dtype=REG_DTYPE.S32,
        access=REG_ACCESS.RW,
    )
    RPDO_ASSIGN_REGISTER_SUB_IDX_1 = EthercatRegister(
        identifier="RPDO_ASSIGN_REGISTER",
        units="",
        subnode=0,
        idx=0x1C12,
        subidx=0x01,
        dtype=REG_DTYPE.S32,
        access=REG_ACCESS.RW,
    )
    RPDO_MAP_REGISTER_SUB_IDX_0 = EthercatRegister(
        identifier="RPDO_MAP_REGISTER",
        units="",
        subnode=0,
        idx=0x1600,
        subidx=0x00,
        dtype=REG_DTYPE.S32,
        access=REG_ACCESS.RW,
    )
    RPDO_MAP_REGISTER_SUB_IDX_1 = EthercatRegister(
        identifier="RPDO_MAP_REGISTER",
        units="",
        subnode=0,
        idx=0x1600,
        subidx=0x01,
        dtype=REG_DTYPE.STR,
        access=REG_ACCESS.RW,
    )
    TPDO_ASSIGN_REGISTER_SUB_IDX_0 = EthercatRegister(
        identifier="TPDO_ASSIGN_REGISTER",
        units="",
        subnode=0,
        idx=0x1C13,
        subidx=0x00,
        dtype=REG_DTYPE.S32,
        access=REG_ACCESS.RW,
    )
    TPDO_ASSIGN_REGISTER_SUB_IDX_1 = EthercatRegister(
        identifier="TPDO_ASSIGN_REGISTER",
        units="",
        subnode=0,
        idx=0x1C13,
        subidx=0x01,
        dtype=REG_DTYPE.S32,
        access=REG_ACCESS.RW,
    )
    TPDO_MAP_REGISTER_SUB_IDX_0 = EthercatRegister(
        identifier="TPDO_MAP_REGISTER",
        units="",
        subnode=0,
        idx=0x1A00,
        subidx=0x00,
        dtype=REG_DTYPE.S32,
        access=REG_ACCESS.RW,
    )
    TPDO_MAP_REGISTER_SUB_IDX_1 = EthercatRegister(
        identifier="TPDO_MAP_REGISTER",
        units="",
        subnode=0,
        idx=0x1A00,
        subidx=0x01,
        dtype=REG_DTYPE.STR,
        access=REG_ACCESS.RW,
    )

    def __init__(self, servo: EthercatServo, pdo_map: PDOMap):
        self.servo = servo
        self.rpdo_registers = pdo_map.rpdo_registers
        self.tpdo_registers = pdo_map.tpdo_registers

    def set_slave_mapping(self, slave_id: int = 1) -> None:
        self.reset_rpdo_mapping()
        self.reset_tpdo_mapping()
        self.map_rpdo()
        self.map_tpdo()

    def reset_rpdo_mapping(self) -> None:
        """Reset the RPDO mappings"""
        self.servo.write(self.RPDO_ASSIGN_REGISTER_SUB_IDX_0, 0)
        self.servo.write(self.RPDO_MAP_REGISTER_SUB_IDX_0, 0)

    def reset_tpdo_mapping(self) -> None:
        """Reset the TPDO mappings"""
        self.servo.write(self.TPDO_ASSIGN_REGISTER_SUB_IDX_0, 0)
        self.servo.write(self.TPDO_MAP_REGISTER_SUB_IDX_0, 0)

    def map_rpdo(self) -> None:
        """Map the RPDO registers"""
        rpdo_map = bytes()
        for pdo_map_item in self.rpdo_registers:
            rpdo_map += self.map_register(pdo_map_item.register)  # type: ignore
        self.servo.write(self.RPDO_MAP_REGISTER_SUB_IDX_0, len(self.rpdo_registers))
        self.servo.write(
            self.RPDO_MAP_REGISTER_SUB_IDX_1, rpdo_map.decode("utf-8"), complete_access=True
        )
        self.servo.write(self.RPDO_ASSIGN_REGISTER_SUB_IDX_0, 1)
        self.servo.write(
            self.RPDO_ASSIGN_REGISTER_SUB_IDX_1,
            self.RPDO_MAP_REGISTER_SUB_IDX_0.idx,
            complete_access=True,
        )

    def map_tpdo(self) -> None:
        """Map the TPDO registers."""
        tpdo_map = bytes()
        for pdo_map_item in self.tpdo_registers:
            tpdo_map += self.map_register(pdo_map_item.register)  # type: ignore
        self.servo.write(self.TPDO_MAP_REGISTER_SUB_IDX_0, len(self.tpdo_registers))
        self.servo.write(
            self.TPDO_MAP_REGISTER_SUB_IDX_1, tpdo_map.decode("utf-8"), complete_access=True
        )
        self.servo.write(self.TPDO_ASSIGN_REGISTER_SUB_IDX_0, 1)
        self.servo.write(
            self.TPDO_ASSIGN_REGISTER_SUB_IDX_1,
            self.TPDO_MAP_REGISTER_SUB_IDX_0.idx,
            complete_access=True,
        )

    @staticmethod
    def map_register(register: EthercatRegister) -> bytes:
        """Arrange register information into PDO mapping format.

        Args:
            register: Register to map.

        Returns:
            PDO register mapping format.

        """
        index = register.idx
        size_bytes = dtype_value[register.dtype][0]
        mapped_register = (index << 16) | (size_bytes * 8)
        mapped_register_bytes: bytes = mapped_register.to_bytes(4, "little")
        return mapped_register_bytes
