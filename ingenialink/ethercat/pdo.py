from dataclasses import dataclass
from typing import List, Callable, Optional

from ingenialink.ethercat.register import EthercatRegister
from ingenialink.utils._utils import convert_dtype_to_bytes, convert_bytes_to_dtype, dtype_value
from ingenialink.register import REG_DTYPE, REG_ACCESS


@dataclass
class PDOMap:
    rpdo_registers: List
    tpdo_registers: List
    rpdo_callback: Callable
    tpdo_callback: Callable
    rpdo_dtypes: Optional[List] = None
    tpdo_dtypes: Optional[List] = None


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

    def __init__(self, servo, pdo_mapping_info):
        self.servo = servo
        self.rpdo_registers = pdo_mapping_info.rpdo_registers
        self.tpdo_registers = pdo_mapping_info.tpdo_registers

    def set_slave_mapping(self, slave_id: int = 1):
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
        for register in self.rpdo_registers:
            rpdo_register = self.servo.dictionary.registers(1)[register]
            rpdo_map += self.map_register(rpdo_register)  # type: ignore
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
        for register in self.tpdo_registers:
            tpdo_register = self.servo.dictionary.registers(1)[register]
            tpdo_map += self.map_register(tpdo_register)  # type: ignore
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

    def map_register(self, register: EthercatRegister) -> bytes:
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


class PDOMapping:
    def __init__(self, pdo_mapping_info):
        self.rpdo_dtypes = pdo_mapping_info.rpdo_dtypes
        self.tpdo_dtypes = pdo_mapping_info.tpdo_dtypes
        self.tpdo_callback = pdo_mapping_info.tpdo_callback
        self.rpdo_callback = pdo_mapping_info.rpdo_callback

    def process_inputs(self, input_data):
        inputs = []
        for reg_dtype in self.tpdo_dtypes:
            data_size = dtype_value[reg_dtype][0]
            data = input_data[:data_size]
            input_data = input_data[data_size:]
            inputs.append(convert_bytes_to_dtype(data, reg_dtype))
        self.tpdo_callback(inputs)

    def generate_outputs(self):
        output = bytes()
        for value, reg_dtype in zip(self.rpdo_callback(), self.rpdo_dtypes):
            output += convert_dtype_to_bytes(value, reg_dtype)
        return output