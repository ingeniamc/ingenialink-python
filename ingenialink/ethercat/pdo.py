from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Callable, TYPE_CHECKING, Optional, Any, Union

from ingenialink.ethercat.register import EthercatRegister
from ingenialink.utils._utils import dtype_value
from ingenialink.register import Register, REG_DTYPE, REG_ACCESS
from ingenialink.dictionary import Dictionary

if TYPE_CHECKING:
    from ingenialink.ethercat.servo import EthercatServo


class PDOType(Enum):
    TPDO = auto()
    RDPO = auto()


@dataclass
class PDOMapItem:
    register: Register
    callback: Callable[["PDOMapItem"], Union[int, float, str, bytes]]
    value: Optional[Any] = None


@dataclass
class PDOMap:
    dictionary: Dictionary
    rpdo_registers: List[PDOMapItem] = field(default_factory=list)
    tpdo_registers: List[PDOMapItem] = field(default_factory=list)

    def add_register(
        self,
        register: str,
        callback: Callable[["PDOMapItem"], Any],
        pdo_type: PDOType,
        axis: int = 1,
    ) -> None:
        """
        Adds a register to the PDO map.

        Args:
            register: the register UID.
            callback: In the case of an RPDO register the function from where to retrieve the value to be set.
            In the case of a TPDO register, the function to send the register value.
            pdo_type: Whether the register is a TPDO or RPDO.
            axis: register axis.

        """
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

    def __init__(self, servo: "EthercatServo", pdo_map: PDOMap):
        """Mapper for TPDO and RPDO registers.

        Args:
            servo: Servo instance to map the PDOs into.
            pdo_map: PDO mapping information.

        """
        self.servo = servo
        self.rpdo_registers = pdo_map.rpdo_registers
        self.tpdo_registers = pdo_map.tpdo_registers

    def set_slave_mapping(self) -> None:
        """Map the PDOs according to the PDO Map"""
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
            rpdo_map += self.map_register(pdo_map_item.register)
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
            tpdo_map += self.map_register(pdo_map_item.register)
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
    def map_register(register: Register) -> bytes:
        """Arrange register information into PDO mapping format.

        Args:
            register: Register to map.

        Returns:
            PDO register mapping format.

        """
        if not isinstance(register, EthercatRegister):
            raise NotImplementedError(
                f"PDO mapping not supported for register type: {type(register)}"
            )
        index = register.idx
        size_bytes = dtype_value[register.dtype][0]
        mapped_register = (index << 16) | (size_bytes * 8)
        mapped_register_bytes: bytes = mapped_register.to_bytes(4, "little")
        return mapped_register_bytes
