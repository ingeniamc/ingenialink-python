from typing import List, Optional, Union, Dict

import bitarray

from ingenialink.canopen.register import CanopenRegister
from ingenialink.enums.register import REG_DTYPE, REG_ACCESS, RegCyclicType
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.exceptions import ILError
from ingenialink.servo import Servo
from ingenialink.utils._utils import (
    convert_bytes_to_dtype,
    convert_dtype_to_bytes,
    dtype_length_bits,
)

BIT_ENDIAN = "little"
bitarray._set_default_endian(BIT_ENDIAN)

PADDING_REGISTER_IDENTIFIER = "PADDING"


class PDOMapItem:
    """Abstract class to represent a register in the PDO mapping.

    Attributes:
        register: mapped register object. If None the item will padding.
        size_bits: custom register size in bits.

    Raises:
        ValueError: If the register and size_bits are not provided.
        ValueError: If the size_bits value is invalid. Only when the register
        is set to None.

    """

    ACCEPTED_CYCLIC: RegCyclicType
    """Accepted cyclic: CYCLIC_TX, CYCLIC_RX or CYCLIC_TXRX."""

    def __init__(
        self,
        register: Union[None, EthercatRegister, CanopenRegister] = None,
        size_bits: Optional[int] = None,
    ) -> None:
        if register is None:
            if size_bits is None:
                raise ValueError("The size bits must be set when creating padding items.")
            register = EthercatRegister(
                identifier=PADDING_REGISTER_IDENTIFIER,
                units="",
                subnode=0,
                idx=0x0000,
                subidx=0x00,
                cyclic=self.ACCEPTED_CYCLIC,
                dtype=REG_DTYPE.STR,
                access=REG_ACCESS.RW,
            )
        self.register = register
        self.size_bits = size_bits or dtype_length_bits[register.dtype]
        self._raw_data_bits: Optional[bitarray.bitarray] = None
        self._check_if_mappable()

    def _check_if_mappable(self) -> None:
        """Check if the passed register is mappable. I.e., if the cyclic information is correct.

        Raises:
            ILError: Tf the register is not mappable.
        """
        if self.register.cyclic not in [self.ACCEPTED_CYCLIC, RegCyclicType.TXRX]:
            raise ILError(
                f"Incorrect cyclic. It should be {self.ACCEPTED_CYCLIC} or {RegCyclicType.TXRX},"
                f" obtained: {self.register.cyclic}"
            )

    @property
    def raw_data_bits(self) -> bitarray.bitarray:
        """Raw data in bits.

        Returns:
            Raw data in bits

        Raises:
            ILError: If the raw data is empty.

        """
        if self._raw_data_bits is None:
            raise ILError("Raw data is empty.")
        return self._raw_data_bits

    @raw_data_bits.setter
    def raw_data_bits(self, data: bitarray.bitarray) -> None:
        if len(data) != self.size_bits:
            raise ILError(f"Wrong size. Expected {self.size_bits}, obtained {len(data)}")
        if data.endian() != BIT_ENDIAN:
            raise ILError("Bitarray should be little endian.")
        self._raw_data_bits = data

    @property
    def raw_data_bytes(self) -> bytes:
        """Raw data in bytes.

        Returns:
            Raw data in bytes

        Raises:
            ILError: If the raw data is empty.

        """
        if self._raw_data_bits is None:
            raise ILError("Raw data is empty.")
        return self._raw_data_bits.tobytes()

    @raw_data_bytes.setter
    def raw_data_bytes(self, data: bytes) -> None:
        data_bits = bitarray.bitarray(endian=BIT_ENDIAN)
        data_bits.frombytes(data)
        if self.register.identifier == PADDING_REGISTER_IDENTIFIER:
            data_bits = data_bits[: self.size_bits]
        self.raw_data_bits = data_bits

    @property
    def value(self) -> Union[int, float, bool]:
        """Register value. Converts the raw data bytes into the register value.

        Raises:
            ILError: If the raw data is empty.
            ILError: If the register type is not int or float.

        Returns:
            Register value.
        """
        value: Union[bool, int, float, str]
        if self.register.identifier == PADDING_REGISTER_IDENTIFIER:
            raise NotImplementedError(
                "The register value must be read by the raw_data_bytes attribute."
            )
        if self.register.dtype == REG_DTYPE.BOOL:
            value = self.raw_data_bits.any()
        else:
            value = convert_bytes_to_dtype(self.raw_data_bytes, self.register.dtype)
        if not isinstance(value, (int, float, bool)):
            raise ILError("Wrong register value type")
        return value

    @property
    def register_mapping(self) -> bytes:
        """Arrange register information into PDO mapping format.

        Returns:
            PDO register mapping format.

        """
        index = self.register.idx
        mapped_register = (index << 16) | self.size_bits
        mapped_register_bytes: bytes = mapped_register.to_bytes(4, "little")
        return mapped_register_bytes


class RPDOMapItem(PDOMapItem):
    """Class to represent RPDO mapping items."""

    ACCEPTED_CYCLIC = RegCyclicType.RX

    def __init__(
        self,
        register: Union[None, EthercatRegister, CanopenRegister] = None,
        size_bits: Optional[int] = None,
    ) -> None:
        super().__init__(register, size_bits)

    @property
    def value(self) -> Union[int, float]:
        return super().value

    @value.setter
    def value(self, value: Union[int, float, bool]) -> None:
        if self.register.identifier == PADDING_REGISTER_IDENTIFIER:
            raise NotImplementedError(
                "The register value must be set by the raw_data_bytes attribute."
            )
        if isinstance(value, bool):
            raw_data_bits = bitarray.bitarray(endian=BIT_ENDIAN)
            raw_data_bits.append(value)
            self.raw_data_bits = raw_data_bits
        else:
            raw_data_bytes = convert_dtype_to_bytes(value, self.register.dtype)
            self.raw_data_bytes = raw_data_bytes


class TPDOMapItem(PDOMapItem):
    """Class to represent TPDO mapping items."""

    ACCEPTED_CYCLIC = RegCyclicType.TX


class PDOMap:
    """Abstract class that contains PDO mapping information."""

    _PDO_MAP_ITEM_CLASS = PDOMapItem

    def __init__(self) -> None:
        self.__items: List[PDOMapItem] = []
        self.__map_register_address: Optional[int] = None

    def create_item(
        self, register: Union[EthercatRegister, CanopenRegister], size_bits: Optional[int] = None
    ) -> PDOMapItem:
        """Create a new PDOMapItem.

        Args:
            register: Register object.
            size_bits: Register size in bits.

        Returns:
            PDO Map item.
        """
        item = self._PDO_MAP_ITEM_CLASS(register, size_bits)
        return item

    def add_item(self, item: PDOMapItem) -> None:
        """Append a new item.

        Args:
            item: Item to be added.
        """
        self.__items.append(item)

    def add_registers(
        self,
        registers: Union[
            Union[EthercatRegister, CanopenRegister], List[Union[EthercatRegister, CanopenRegister]]
        ],
    ) -> None:
        """Add a register or a list of registers in bulk.

        It creates a new item for each register and adds it the items attribute.

        Args:
            registers: Register object or list of Registers.
        """
        if not isinstance(registers, list):
            registers = [registers]
        for register in registers:
            item = self.create_item(register)
            self.add_item(item)

    @property
    def items(self) -> List[PDOMapItem]:
        """List of items.

        Returns:
            List of items.
        """
        return self.__items

    @property
    def map_register_index_bytes(self) -> bytes:
        """Index of the mapping register in bytes.

        Returns:
            Index of the mapping register in bytes.

        Raises:
            ValueError: If map_register_index is None
        """
        if self.map_register_index is None:
            raise ValueError("map_register_index is None")
        else:
            return self.map_register_index.to_bytes(4, "little")

    @property
    def map_register_index(self) -> Optional[int]:
        """Index of the mapping register. None if it is not mapped in the slave.

        Returns:
            Index of the mapping register.
        """
        return self.__map_register_address

    @map_register_index.setter
    def map_register_index(self, address: int) -> None:
        self.__map_register_address = address

    @property
    def data_length_bits(self) -> int:
        """Length of the map in bits.

        Returns:
            Length of the map in bits.
        """
        return sum(item.size_bits for item in self.items)

    @property
    def data_length_bytes(self) -> int:
        """Length of the map in bytes.

        Returns:
            Length of the map in bytes.
        """
        return bitarray.bits2bytes(self.data_length_bits)

    @property
    def items_mapping(self) -> bytearray:
        """Returns all register item mappings concatenated.

        Returns:
            int: _description_
        """
        map_bytes = bytearray()
        for pdo_map_item in self.items:
            map_bytes += pdo_map_item.register_mapping
        return map_bytes

    def set_item_bytes(self, data_bytes: bytes) -> None:
        """Set the items raw data from a byte array.

        Args:
            data_bytes: Byte array.

        Raises:
            ILError: If the length of the received data does not coincide.
        """
        if len(data_bytes) != self.data_length_bytes:
            raise ILError(
                f"The length of the data array is incorrect. Expected {self.data_length_bytes},"
                f" obtained {len(data_bytes)}"
            )
        data_bits = bitarray.bitarray(endian=BIT_ENDIAN)
        data_bits.frombytes(data_bytes)

        offset = 0
        for item in self.items:
            item.raw_data_bits = data_bits[offset : item.size_bits + offset]
            offset += item.size_bits

    def get_item_bits(self) -> bitarray.bitarray:
        """Return the concatenated items raw data (in bits).

        Raises:
            ILError: Raw data is empty.
            ILError: If the length of the bit array is incorrect.

        Returns:
            Concatenated items raw data in bits.
        """
        data_bits = bitarray.bitarray(endian=BIT_ENDIAN)
        for item in self.items:
            try:
                data_bits += item.raw_data_bits
            except ILError:
                raise ILError(f"PDO item {item.register.identifier} does not have data stored.")

        if len(data_bits) != self.data_length_bits:
            raise ILError(
                "The length in bits of the data array is incorrect. Expected"
                f" {self.data_length_bits}, obtained {len(data_bits)}"
            )
        return data_bits

    def get_item_bytes(self) -> bytes:
        """Return the concatenated items raw data (in bytes).

        Raises:
            ILError: Raw data is empty.
            ILError: If the length of th byte array is incorrect.

        Returns:
            Concatenated items raw data in bytes.
        """
        item_bits = self.get_item_bits()
        return item_bits.tobytes()


class RPDOMap(PDOMap):
    """Class to store RPDO mapping information."""

    _PDO_MAP_ITEM_CLASS = RPDOMapItem


class TPDOMap(PDOMap):
    """Class to store TPDO mapping information."""

    _PDO_MAP_ITEM_CLASS = TPDOMapItem


class PDOServo(Servo):
    """Abstract class to implement PDOs in a Servo class."""

    AVAILABLE_PDOS = 1

    RPDO_ASSIGN_REGISTER_SUB_IDX_0 = "RPDO_ASSIGN_REGISTER_SUB_IDX_0"
    RPDO_ASSIGN_REGISTER_SUB_IDX_1 = "RPDO_ASSIGN_REGISTER_SUB_IDX_1"
    RPDO_MAP_REGISTER_SUB_IDX_0 = ["RPDO_MAP_REGISTER_SUB_IDX_0"]
    RPDO_MAP_REGISTER_SUB_IDX_1 = ["RPDO_MAP_REGISTER_SUB_IDX_1"]

    TPDO_ASSIGN_REGISTER_SUB_IDX_0 = "TPDO_ASSIGN_REGISTER_SUB_IDX_0"
    TPDO_ASSIGN_REGISTER_SUB_IDX_1 = "TPDO_ASSIGN_REGISTER_SUB_IDX_1"
    TPDO_MAP_REGISTER_SUB_IDX_0 = ["TPDO_MAP_REGISTER_SUB_IDX_0"]
    TPDO_MAP_REGISTER_SUB_IDX_1 = ["TPDO_MAP_REGISTER_SUB_IDX_1"]

    def __init__(
        self,
        target: Union[int, str],
        dictionary_path: str,
        servo_status_listener: bool = False,
    ):
        super().__init__(target, dictionary_path, servo_status_listener)
        self._rpdo_maps: List[RPDOMap] = []
        self._tpdo_maps: List[TPDOMap] = []

    def reset_rpdo_mapping(self) -> None:
        """Delete the RPDO mapping stored in the servo slave."""
        self.write(self.RPDO_ASSIGN_REGISTER_SUB_IDX_0, 0, subnode=0)
        for map_register in self.RPDO_MAP_REGISTER_SUB_IDX_0:
            self.write(map_register, 0, subnode=0)
        self._rpdo_maps.clear()

    def reset_tpdo_mapping(self) -> None:
        """Delete the TPDO mapping stored in the servo slave."""
        self.write(self.TPDO_ASSIGN_REGISTER_SUB_IDX_0, 0, subnode=0)
        for map_register in self.TPDO_MAP_REGISTER_SUB_IDX_0:
            self.write(map_register, 0, subnode=0)
        self._tpdo_maps.clear()

    def map_rpdos(self) -> None:
        """Map the RPDO registers into the servo slave.
        It takes the first available RPDO assignment slot of the slave.

        Raises:
            ILError: If there are no available PDOs.
        """
        if len(self._rpdo_maps) > self.AVAILABLE_PDOS:
            raise ILError(
                f"Could not map the RPDO maps, received {len(self._rpdo_maps)} PDOs and only"
                f" {self.AVAILABLE_PDOS} are available"
            )
        self.write(self.RPDO_ASSIGN_REGISTER_SUB_IDX_0, len(self._rpdo_maps), subnode=0)
        custom_map_index = 0
        rpdo_assigns = b""
        for rpdo_map in self._rpdo_maps:
            if rpdo_map.map_register_index is None:
                self._set_rpdo_map_register(custom_map_index, rpdo_map)
                custom_map_index += 1
            rpdo_assigns += rpdo_map.map_register_index_bytes
        self.write(
            self.RPDO_ASSIGN_REGISTER_SUB_IDX_1, rpdo_assigns, complete_access=True, subnode=0
        )

    def _set_rpdo_map_register(self, rpdo_map_register_index: int, rpdo_map: RPDOMap) -> None:
        """Fill RPDO map register with PRDOMap object data

        Args:
            rpdo_map_register_index: custom rpdo map register index
            rpdo_map: custom rpdo data

        """
        self.write(
            self.RPDO_MAP_REGISTER_SUB_IDX_0[rpdo_map_register_index],
            len(rpdo_map.items),
            subnode=0,
        )
        self.write(
            self.RPDO_MAP_REGISTER_SUB_IDX_1[rpdo_map_register_index],
            rpdo_map.items_mapping.decode("utf-8"),
            complete_access=True,
            subnode=0,
        )
        rpdo_map_register = self.dictionary.registers(0)[
            self.RPDO_MAP_REGISTER_SUB_IDX_0[rpdo_map_register_index]
        ]
        if not isinstance(rpdo_map_register, EthercatRegister):
            raise ValueError(
                "Error retrieving the RPDO Map register. Expected EthercatRegister, got:"
                f" {type(rpdo_map_register)}"
            )
        rpdo_map.map_register_index = rpdo_map_register.idx

    def map_tpdos(self) -> None:
        """Map the TPDO registers into the servo slave.
        It takes the first available TPDO assignment slot of the slave.

        Raises:
            ILError: If there are no available PDOs.
        """
        if len(self._tpdo_maps) > self.AVAILABLE_PDOS:
            raise ILError(
                f"Could not map the TPDO maps, received {len(self._tpdo_maps)} PDOs and only"
                f" {self.AVAILABLE_PDOS} are available"
            )
        self.write(self.TPDO_ASSIGN_REGISTER_SUB_IDX_0, len(self._tpdo_maps), subnode=0)
        custom_map_index = 0
        tpdo_assigns = b""
        for tpdo_map in self._tpdo_maps:
            if tpdo_map.map_register_index is None:
                self._set_tpdo_map_register(custom_map_index, tpdo_map)
                custom_map_index += 1
            tpdo_assigns += tpdo_map.map_register_index_bytes
        self.write(
            self.TPDO_ASSIGN_REGISTER_SUB_IDX_1, tpdo_assigns, complete_access=True, subnode=0
        )

    def _set_tpdo_map_register(self, tpdo_map_register_index: int, tpdo_map: TPDOMap) -> None:
        """Fill TPDO map register with TRDOMap object data

        Args:
            tpdo_map_register_index: custom tpdo map register index
            tpdo_map: custom tpdo data

        """
        self.write(
            self.TPDO_MAP_REGISTER_SUB_IDX_0[tpdo_map_register_index],
            len(tpdo_map.items),
            subnode=0,
        )
        self.write(
            self.TPDO_MAP_REGISTER_SUB_IDX_1[tpdo_map_register_index],
            tpdo_map.items_mapping.decode("utf-8"),
            complete_access=True,
            subnode=0,
        )
        tpdo_map_register = self.dictionary.registers(0)[
            self.TPDO_MAP_REGISTER_SUB_IDX_0[tpdo_map_register_index]
        ]
        if not isinstance(tpdo_map_register, EthercatRegister):
            raise ValueError(
                "Error retrieving the TPDO Map register. Expected EthercatRegister, got:"
                f" {type(tpdo_map_register)}"
            )
        tpdo_map.map_register_index = tpdo_map_register.idx

    def map_pdos(self, slave_index: int) -> None:
        """Map RPDO and TPDO register into the slave.

        Args:
            slave_index: salve index.
        """
        self.map_tpdos()
        self.map_rpdos()

    def reset_pdo_mapping(self) -> None:
        """Reset the RPDO and TPDO mapping in the slave."""
        self.reset_rpdo_mapping()
        self.reset_tpdo_mapping()

    def remove_rpdo_map(
        self, rpdo_map: Optional[RPDOMap] = None, rpdo_map_index: Optional[int] = None
    ) -> None:
        """Remove a RPDOMap from the RPDOMap list.

        Args:
            rpdo_map: The RPDOMap instance to be removed.
            rpdo_map_index: The index of the RPDOMap list to be removed.

        Raises:
            ValueError: If the RPDOMap instance is not in the RPDOMap list.
            IndexError: If the index is out of range.

        """
        if rpdo_map_index is None and rpdo_map is None:
            raise ValueError("The RPDOMap instance or the index should be provided.")
        if rpdo_map is not None:
            self._rpdo_maps.remove(rpdo_map)
            return
        if rpdo_map_index is not None:
            self._rpdo_maps.pop(rpdo_map_index)

    def remove_tpdo_map(
        self, tpdo_map: Optional[TPDOMap] = None, tpdo_map_index: Optional[int] = None
    ) -> None:
        """Remove a TPDOMap from the TPDOMap list.

        Args:
            tpdo_map: The TPDOMap instance to be removed.
            tpdo_map_index: The index of the TPDOMap list to be removed.

        Raises:
            ValueError: If the TPDOMap instance is not in the TPDOMap list.
            IndexError: If the index is out of range.

        """
        if tpdo_map_index is None and tpdo_map is None:
            raise ValueError("The TPDOMap instance or the index should be provided.")
        if tpdo_map is not None:
            self._tpdo_maps.remove(tpdo_map)
            return
        if tpdo_map_index is not None:
            self._tpdo_maps.pop(tpdo_map_index)

    def set_pdo_map_to_slave(self, rpdo_maps: List[RPDOMap], tpdo_maps: List[TPDOMap]) -> None:
        """Callback called by the slave to configure the map.

        Args:
            rpdo_maps: List of RPDO maps.
            tpdo_maps: List of TPDO maps.
        """
        raise NotImplementedError

    def process_pdo_inputs(self) -> None:
        """Process the PDO inputs.

        It should call _process_rpdo method to obtain the bytes to be sent to the slave.
        """
        raise NotImplementedError

    def generate_pdo_outputs(self) -> None:
        """Process the PDO outputs.

        It should call _process_tpdo method using the received bytes as argument.
        """
        raise NotImplementedError

    def _process_tpdo(self, input_data: bytes) -> None:
        """Convert the TPDO values from bytes to the registers data type.

        Args:
            input_data: Concatenated received data bytes.

        """
        if len(self._tpdo_maps) == 0:
            return
        for tpdo_map in self._tpdo_maps:
            map_bytes = input_data[: tpdo_map.data_length_bytes]
            tpdo_map.set_item_bytes(map_bytes)

    def _process_rpdo(self) -> Optional[bytes]:
        """Retrieve the RPDO raw data from each map.

        Return:
            Concatenated data bytes to be sent.
        """
        if len(self._rpdo_maps) == 0:
            return None
        output = bytearray()
        for rpdo_map in self._rpdo_maps:
            output += rpdo_map.get_item_bytes()
        return bytes(output)
