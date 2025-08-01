from abc import abstractmethod
from typing import TYPE_CHECKING, Callable, ClassVar, Literal, Optional, TypeVar, Union

import bitarray
from typing_extensions import override

from ingenialink.bitfield import BitField
from ingenialink.canopen.dictionary import CanopenDictionary
from ingenialink.canopen.register import CanopenRegister
from ingenialink.enums.register import RegAccess, RegCyclicType, RegDtype
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.exceptions import ILError
from ingenialink.servo import Servo
from ingenialink.utils._utils import (
    convert_bytes_to_dtype,
    convert_dtype_to_bytes,
    dtype_length_bits,
)

if TYPE_CHECKING:
    from ingenialink.dictionary import CanOpenObject

BIT_ENDIAN: Literal["little"] = "little"
bitarray._set_default_endian(BIT_ENDIAN)

PADDING_REGISTER_IDENTIFIER = "PADDING"

MAP_REGISTER_BYTES = 4
"""Number of bytes used to store each mapping register information."""


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

    ACCEPTED_CYCLICS: tuple[RegCyclicType, ...]
    """Accepted cyclic: CYCLIC_TX, CYCLIC_RX, CYCLIC_SI, CYCLIC_SO, CYCLIC_SISO."""

    __LENGTH_BITFIELD = "LENGTH"
    __SUBINDEX_BITFIELD = "SUBINDEX"
    __INDEX_BITFIELD = "INDEX"

    __ITEM_BITFIELDS: ClassVar[dict[str, BitField]] = {
        __LENGTH_BITFIELD: BitField(0, 7),
        __SUBINDEX_BITFIELD: BitField(8, 15),
        __INDEX_BITFIELD: BitField(16, 31),
    }

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
                pdo_access=self.ACCEPTED_CYCLICS[0],
                dtype=RegDtype.STR,
                access=RegAccess.RW,
            )
        self.register = register
        self.size_bits = size_bits or dtype_length_bits[register.dtype]
        self._raw_data_bits: Optional[bitarray.bitarray] = None
        self._check_if_mappable()

    def _check_if_mappable(self) -> None:
        """Check if the passed register is mappable. I.e., if the pdo_access information is correct.

        Raises:
            ILError: Tf the register is not mappable.
        """
        if self.register.pdo_access not in self.ACCEPTED_CYCLICS:
            formatted_accepted = ", ".join([str(cyclic) for cyclic in self.ACCEPTED_CYCLICS])

            raise ILError(
                f"Incorrect pdo access for mapping register {self.register.identifier}. "
                f"It should be {formatted_accepted}."
                f" obtained: {self.register.pdo_access}"
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
    def value(self) -> Union[int, float, bool, bytes]:
        """Register value. Converts the raw data bytes into the register value.

        Raises:
            ILError: If the raw data is empty.
            ILError: If the register type is not int or float.

        Returns:
            Register value.
        """
        value: Union[bool, int, float, str, bytes]
        if self.register.identifier == PADDING_REGISTER_IDENTIFIER:
            raise NotImplementedError(
                "The register value must be read by the raw_data_bytes attribute."
            )
        if self.register.dtype == RegDtype.BOOL:
            value = self.raw_data_bits.any()
        else:
            value = convert_bytes_to_dtype(self.raw_data_bytes, self.register.dtype)
        if not isinstance(value, (int, float, bool)):
            raise ILError("Wrong register value type")
        return value

    @property
    def register_mapping(self) -> int:
        """Arrange register information into PDO mapping format.

        Returns:
            PDO register mapping format.

        """
        return BitField.set_bitfields(
            self.__ITEM_BITFIELDS,
            {
                self.__LENGTH_BITFIELD: self.size_bits,
                self.__SUBINDEX_BITFIELD: self.register.subidx,
                self.__INDEX_BITFIELD: self.register.idx,
            },
        )

    @classmethod
    def from_register_mapping(cls, mapping: int, dictionary: "CanopenDictionary") -> "PDOMapItem":
        """Create a PDOMapItem from a register mapping.

        Args:
            mapping: Register mapping in bytes.
            dictionary: Canopen dictionary to retrieve the registers.

        Returns:
            PDOMapItem instance.
        """
        fields = BitField.parse_bitfields(cls.__ITEM_BITFIELDS, mapping)
        size_bits = fields[cls.__LENGTH_BITFIELD]
        index = fields[cls.__INDEX_BITFIELD]
        subindex = fields[cls.__SUBINDEX_BITFIELD]

        if index == 0 and subindex == 0:
            # This is a padding register, return a padding item.
            return cls(size_bits=size_bits)

        try:
            register = dictionary.get_register_by_index_subindex(index, subindex)
        except KeyError:
            register = EthercatRegister(
                identifier="UNKNOWN_REGISTER",
                units="",
                subnode=0,
                idx=index,
                subidx=subindex,
                pdo_access=cls.ACCEPTED_CYCLICS[0],
                dtype=RegDtype.STR,
                access=RegAccess.RW,
            )
        return cls(register, size_bits)

    def __repr__(self) -> str:
        """String representation of the PDOMapItem class.

        Returns:
            str: String representation of the PDOMapItem instance.
        """
        return (
            f"<{self.__class__.__name__} {self.register.identifier} "
            f"({self.size_bits} bits) at 0x{id(self):X} >"
        )


class RPDOMapItem(PDOMapItem):
    """Class to represent RPDO mapping items."""

    ACCEPTED_CYCLICS = (
        RegCyclicType.RX,
        RegCyclicType.SAFETY_OUTPUT,
        RegCyclicType.SAFETY_INPUT_OUTPUT,
    )

    def __init__(
        self,
        register: Union[None, EthercatRegister, CanopenRegister] = None,
        size_bits: Optional[int] = None,
    ) -> None:
        super().__init__(register, size_bits)

    @override
    @property
    def value(self) -> Union[int, float, bytes]:
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

    ACCEPTED_CYCLICS = (
        RegCyclicType.TX,
        RegCyclicType.SAFETY_INPUT,
        RegCyclicType.SAFETY_INPUT_OUTPUT,
    )


PDO_MAP_TYPE = TypeVar("PDO_MAP_TYPE", bound="PDOMap")


class PDOMap:
    """Abstract class that contains PDO mapping information."""

    _PDO_MAP_ITEM_CLASS = PDOMapItem

    def __init__(self) -> None:
        self.__items: list[PDOMapItem] = []
        self.__map_register_index: Optional[int] = None
        self.__map_object: Optional[CanOpenObject] = None
        self.__slave: Optional[PDOServo] = None

    @property
    def slave(self) -> Optional["PDOServo"]:
        """Servo to which this PDO is mapped, None if it's not mapped to any servo."""
        return self.__slave

    @slave.setter
    def slave(self, slave: Optional["PDOServo"]) -> None:
        self.__slave = slave

    def __check_servo_is_in_preoperational_state(self) -> None:
        if self.slave is not None:
            self.slave.check_servo_is_in_preoperational_state()

    def create_item(
        self, register: Union[EthercatRegister, CanopenRegister], size_bits: Optional[int] = None
    ) -> PDOMapItem:
        """Create a new PDOMapItem.

        WARNING: This operation can not be done if the servo is not in pre-operational state.

        Args:
            register: Register object.
            size_bits: Register size in bits.

        Returns:
            PDO Map item.
        """
        self.__check_servo_is_in_preoperational_state()
        item = self._PDO_MAP_ITEM_CLASS(register, size_bits)
        return item

    def add_item(self, item: PDOMapItem) -> None:
        """Append a new item.

        WARNING: This operation can not be done if the servo is not in pre-operational state.

        Args:
            item: Item to be added.
        """
        self.__check_servo_is_in_preoperational_state()
        self.__items.append(item)

    def add_registers(
        self,
        registers: Union[
            Union[EthercatRegister, CanopenRegister], list[Union[EthercatRegister, CanopenRegister]]
        ],
    ) -> None:
        """Add a register or a list of registers in bulk.

        It creates a new item for each register and adds it the items attribute.

        WARNING: This operation can not be done if the servo is not in pre-operational state.

        Args:
            registers: Register object or list of Registers.
        """
        self.__check_servo_is_in_preoperational_state()
        if not isinstance(registers, list):
            registers = [registers]
        for register in registers:
            item = self.create_item(register)
            self.add_item(item)

    @property
    def items(self) -> list[PDOMapItem]:
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
            return self.map_register_index.to_bytes(2, BIT_ENDIAN)

    @property
    def map_register_index(self) -> Optional[int]:
        """Index of the mapping register. None if it is not mapped in the slave.

        Returns:
            Index of the mapping register.
        """
        return self.__map_register_index

    @map_register_index.setter
    def map_register_index(self, index: int) -> None:
        self.__map_register_index = index

    @property
    def map_object(self) -> Optional["CanOpenObject"]:
        """CanOpen object of the mapping register.

        Returns:
            CanOpen object of the mapping register.
        """
        return self.__map_object

    @map_object.setter
    def map_object(self, map_obj: "CanOpenObject") -> None:
        """Set the CanOpen object of the mapping register."""
        self.__map_object = map_obj
        self.__map_register_index = map_obj.idx

    def map_register_values(self) -> dict[CanopenRegister, Optional[int]]:
        """Returns a dictionary with the mapping of the register items.

        Associates which pdo mapping value will have each map register
        Unused mapping registers will return as None.

        This method does not write the mapping to the slave,
        or express what the mapping on the slave should be.
        Use PDOMap.write_to_slave method instead

        Raises:
            ValueError: If the map_object is None.
                The map_object must be set before calling this method.

        Returns:
            dictionary with mapping register as keys and mapping value or None as values.
        """
        if self.map_object is None:
            raise ValueError("The map_object must be set.")

        items_iter = iter(self.items)

        mapping: dict[CanopenRegister, Optional[int]] = {}

        for map_register in self.map_object.registers:
            if map_register.subidx == 0:
                # Used to store the number of items
                mapping[map_register] = len(self.items)
                continue
            try:
                mapping[map_register] = next(items_iter).register_mapping
            except StopIteration:
                # Element of the pdo object mapping unused
                mapping[map_register] = None

        return mapping

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
            map_bytes += pdo_map_item.register_mapping.to_bytes(MAP_REGISTER_BYTES, BIT_ENDIAN)
        return map_bytes

    def to_pdo_value(self) -> bytes:
        """Convert the PDOMap to the full pdo value (accessed via complete access).

        Returns:
            Value of the pdo mapping in bytes.
        """
        return (
            len(self.items).to_bytes(
                length=1, byteorder=BIT_ENDIAN
            )  # First byte is the number of items
            + b"\x00"  # Second byte is padding
            + self.items_mapping
        )

    @classmethod
    def from_pdo_value(
        cls: type[PDO_MAP_TYPE],
        value: bytes,
        map_obj: "CanOpenObject",
        dictionary: "CanopenDictionary",
    ) -> PDO_MAP_TYPE:
        """Create a PDOMap from the full pdo value (accessed via complete access).

        Args:
            value: Value of the pdo mapping in bytes.
            map_obj: Mapping Canopen object.
            dictionary: Canopen dictionary to retrieve the registers.

        Returns:
            PDOMap instance.
        """
        pdo_map = cls()
        pdo_map.map_object = map_obj

        # First element of 8 bits, indicates the number of elements in the mapping.
        n_elements = value[0]

        # Second byte is padding

        for i in range(n_elements):
            # Start reading from the third byte
            item_map = int.from_bytes(
                value[2 + i * MAP_REGISTER_BYTES : 2 + (i + 1) * MAP_REGISTER_BYTES], BIT_ENDIAN
            )
            item = cls._PDO_MAP_ITEM_CLASS.from_register_mapping(item_map, dictionary)
            pdo_map.add_item(item)

        return pdo_map

    def write_to_slave(
        self, max_pdo_items_for_padding: Optional[int] = None, padding: bool = False
    ) -> None:
        """Write the PDOMap to the slave.

        WARNING: This operation can not be done if the servo is not in pre-operational state.

        Args:
            max_pdo_items_for_padding: Maximum number of items for padding. If set, it will pad the
                PDOMap with empty items to reach this number. If None, no padding is done.
            padding: If True, it will force to zero the unused items in the PDOMap.

        Raises:
            ValueError: If the slave is not set or the map_register_index is None.

        """
        self.__check_servo_is_in_preoperational_state()
        if self.__slave is None:
            raise ValueError("To write the PDOMap to the slave, the slave must be set.")
        if self.map_register_index is None:
            raise ValueError(
                "To write the PDOMap to the slave, the map_register_index must be set."
            )

        reg = self.__slave.dictionary.get_register_by_index_subindex(
            self.map_register_index, subindex=0
        )
        value = self.to_pdo_value()
        if padding:
            if self.map_object is None:
                raise ValueError("The map_object must be set to pad the PDOMap.")
            max_pdo_items_for_padding = len(self.map_object.registers) - 1
        if max_pdo_items_for_padding:
            unused_items = max_pdo_items_for_padding - len(self.__items)
            value += b"\x00" * (unused_items * MAP_REGISTER_BYTES)
        self.__slave.write_complete_access(reg, value)

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
        try:
            for item in self.items:
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

        Returns:
            Concatenated items raw data in bytes.
        """
        item_bits = self.get_item_bits()
        return item_bits.tobytes()

    def get_text_representation(self, item_space: int = 40) -> str:
        """Get a text representation of the map.

        Returns:
            str: Text representation of the map.
        """
        grid = [["Item", "Position bytes..bits", "Size bytes..bits"]]

        position_bits = 0
        for item in self.items:
            uid = item.register.identifier
            if uid is None:
                uid = "Unknown register"
            grid.append([
                uid,
                f"{position_bits // 8}..{position_bits % 8}",
                f"{item.size_bits // 8}..{item.size_bits % 8}",
            ])

            position_bits += item.size_bits

        return "\n".join([f"{row[0]:<{item_space}} | {row[1]:<20} | {row[2]:<20}" for row in grid])


class RPDOMap(PDOMap):
    """Class to store RPDO mapping information."""

    _PDO_MAP_ITEM_CLASS = RPDOMapItem


class TPDOMap(PDOMap):
    """Class to store TPDO mapping information."""

    _PDO_MAP_ITEM_CLASS = TPDOMapItem


class PDOServo(Servo):
    """Abstract class to implement PDOs in a Servo class."""

    AVAILABLE_PDOS = 2

    ETG_COMMS_RPDO_ASSIGN_TOTAL = "ETG_COMMS_RPDO_ASSIGN_TOTAL"
    ETG_COMMS_RPDO_ASSIGN_1 = "ETG_COMMS_RPDO_ASSIGN_1"
    ETG_COMMS_RPDO_MAP1_TOTAL = ("ETG_COMMS_RPDO_MAP1_TOTAL",)
    ETG_COMMS_RPDO_MAP1_1 = ("ETG_COMMS_RPDO_MAP1_1",)

    ETG_COMMS_TPDO_ASSIGN_TOTAL = "ETG_COMMS_TPDO_ASSIGN_TOTAL"
    ETG_COMMS_TPDO_ASSIGN_1 = "ETG_COMMS_TPDO_ASSIGN_1"
    ETG_COMMS_TPDO_MAP1_TOTAL = ("ETG_COMMS_TPDO_MAP1_TOTAL",)
    ETG_COMMS_TPDO_MAP1_1 = ("ETG_COMMS_TPDO_MAP1_1",)

    def __init__(
        self,
        target: Union[int, str],
        dictionary_path: str,
        servo_status_listener: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ):
        super().__init__(
            target, dictionary_path, servo_status_listener, disconnect_callback=disconnect_callback
        )
        self._rpdo_maps: list[RPDOMap] = []
        self._tpdo_maps: list[TPDOMap] = []

    @property  # type: ignore[misc]
    def dictionary(self) -> CanopenDictionary:  # type: ignore[override]
        """Canopen dictionary."""
        return self._dictionary  # type: ignore[return-value]

    @abstractmethod
    def check_servo_is_in_preoperational_state(self) -> None:
        """Checks if the servo is in preoperational state.

        Raises:
            ILEcatStateError: if servo is not in preoperational state.
        """
        raise NotImplementedError

    def reset_rpdo_mapping(self) -> None:
        """Delete the RPDO mapping stored in the servo slave.

        WARNING: This operation can not be done if the servo is not in pre-operational state.
        """
        self.check_servo_is_in_preoperational_state()
        self.write(self.ETG_COMMS_RPDO_ASSIGN_TOTAL, 0, subnode=0)
        for map_register in self.ETG_COMMS_RPDO_MAP1_TOTAL:
            self.write(map_register, 0, subnode=0)
        self._rpdo_maps.clear()

    def reset_tpdo_mapping(self) -> None:
        """Delete the TPDO mapping stored in the servo slave.

        WARNING: This operation can not be done if the servo is not in pre-operational state.
        """
        self.check_servo_is_in_preoperational_state()
        self.write(self.ETG_COMMS_TPDO_ASSIGN_TOTAL, 0, subnode=0)
        for map_register in self.ETG_COMMS_TPDO_MAP1_TOTAL:
            self.write(map_register, 0, subnode=0)
        self._tpdo_maps.clear()

    def map_rpdos(self) -> None:
        """Map the RPDO registers into the servo slave.

        It takes the first available RPDO assignment slot of the slave.

        WARNING: This operation can not be done if the servo is not in pre-operational state.

        Raises:
            ILError: If there are no available PDOs.
        """
        self.check_servo_is_in_preoperational_state()
        if len(self._rpdo_maps) > self.AVAILABLE_PDOS:
            raise ILError(
                f"Could not map the RPDO maps, received {len(self._rpdo_maps)} PDOs and only"
                f" {self.AVAILABLE_PDOS} are available"
            )
        self.write(self.ETG_COMMS_RPDO_ASSIGN_TOTAL, len(self._rpdo_maps), subnode=0)
        custom_map_index = 0
        rpdo_assigns = b""
        for rpdo_map in self._rpdo_maps:
            if rpdo_map.map_register_index is None:
                self._set_rpdo_map_register(custom_map_index, rpdo_map)
                custom_map_index += 1
            rpdo_assigns += rpdo_map.map_register_index_bytes
        self.write_complete_access(self.ETG_COMMS_RPDO_ASSIGN_1, rpdo_assigns, subnode=0)

    def _set_rpdo_map_register(self, rpdo_map_register_index: int, rpdo_map: RPDOMap) -> None:
        """Fill RPDO map register with PRDOMap object data.

        Args:
            rpdo_map_register_index: custom rpdo map register index
            rpdo_map: custom rpdo data

        Raises:
            ValueError: If there is an error retrieving the RPDO Map register.
        """
        self.write(
            self.ETG_COMMS_RPDO_MAP1_TOTAL[rpdo_map_register_index],
            len(rpdo_map.items),
            subnode=0,
        )
        self.write_complete_access(
            self.ETG_COMMS_RPDO_MAP1_1[rpdo_map_register_index],
            bytes(rpdo_map.items_mapping),
            subnode=0,
        )
        rpdo_map_register = self.dictionary.registers(0)[
            self.ETG_COMMS_RPDO_MAP1_TOTAL[rpdo_map_register_index]
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

        WARNING: This operation can not be done if the servo is not in pre-operational state.

        Raises:
            ILError: If there are no available PDOs.
        """
        self.check_servo_is_in_preoperational_state()
        if len(self._tpdo_maps) > self.AVAILABLE_PDOS:
            raise ILError(
                f"Could not map the TPDO maps, received {len(self._tpdo_maps)} PDOs and only"
                f" {self.AVAILABLE_PDOS} are available"
            )
        self.write(self.ETG_COMMS_TPDO_ASSIGN_TOTAL, len(self._tpdo_maps), subnode=0)
        custom_map_index = 0
        tpdo_assigns = b""
        for tpdo_map in self._tpdo_maps:
            if tpdo_map.map_register_index is None:
                self._set_tpdo_map_register(custom_map_index, tpdo_map)
                custom_map_index += 1
            tpdo_assigns += tpdo_map.map_register_index_bytes
        self.write_complete_access(self.ETG_COMMS_TPDO_ASSIGN_1, tpdo_assigns, subnode=0)

    def _set_tpdo_map_register(self, tpdo_map_register_index: int, tpdo_map: TPDOMap) -> None:
        """Fill TPDO map register with TRDOMap object data.

        Args:
            tpdo_map_register_index: custom tpdo map register index
            tpdo_map: custom tpdo data

        Raises:
            ValueError: If there is an error retrieving the TPDO Map register.
        """
        self.write(
            self.ETG_COMMS_TPDO_MAP1_TOTAL[tpdo_map_register_index],
            len(tpdo_map.items),
            subnode=0,
        )
        self.write_complete_access(
            self.ETG_COMMS_TPDO_MAP1_1[tpdo_map_register_index],
            bytes(tpdo_map.items_mapping),
            subnode=0,
        )
        tpdo_map_register = self.dictionary.registers(0)[
            self.ETG_COMMS_TPDO_MAP1_TOTAL[tpdo_map_register_index]
        ]
        if not isinstance(tpdo_map_register, EthercatRegister):
            raise ValueError(
                "Error retrieving the TPDO Map register. Expected EthercatRegister, got:"
                f" {type(tpdo_map_register)}"
            )
        tpdo_map.map_register_index = tpdo_map_register.idx

    def map_pdos(self, slave_index: int) -> None:  # noqa: ARG002
        """Map RPDO and TPDO register into the slave.

        WARNING: This operation can not be done if the servo is not in pre-operational state.

        Args:
            slave_index: salve index.
        """
        self.check_servo_is_in_preoperational_state()
        self.map_tpdos()
        self.map_rpdos()

    def reset_pdo_mapping(self) -> None:
        """Reset the RPDO and TPDO mapping in the slave.

        WARNING: This operation can not be done if the servo is not in pre-operational state.
        """
        self.reset_rpdo_mapping()
        self.reset_tpdo_mapping()

    def remove_rpdo_map(
        self, rpdo_map: Optional[RPDOMap] = None, rpdo_map_index: Optional[int] = None
    ) -> None:
        """Remove a RPDOMap from the RPDOMap list.

        WARNING: This operation can not be done if the servo is not in pre-operational state.

        Args:
            rpdo_map: The RPDOMap instance to be removed.
            rpdo_map_index: The index of the RPDOMap list to be removed.

        Raises:
            ValueError: If the RPDOMap instance is not in the RPDOMap list.
        """
        self.check_servo_is_in_preoperational_state()
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

        """
        if tpdo_map_index is None and tpdo_map is None:
            raise ValueError("The TPDOMap instance or the index should be provided.")
        if tpdo_map is not None:
            self._tpdo_maps.remove(tpdo_map)
            return
        if tpdo_map_index is not None:
            self._tpdo_maps.pop(tpdo_map_index)

    def set_pdo_map_to_slave(self, rpdo_maps: list[RPDOMap], tpdo_maps: list[TPDOMap]) -> None:
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
        for tpdo_map in self._tpdo_maps:
            map_bytes = input_data[: tpdo_map.data_length_bytes]
            tpdo_map.set_item_bytes(map_bytes)
            input_data = input_data[tpdo_map.data_length_bytes :]

    def _process_rpdo(self) -> bytes:
        """Retrieve the RPDO raw data from each map.

        Returns:
            Concatenated data bytes to be sent.
        """
        output = bytearray()
        for rpdo_map in self._rpdo_maps:
            output += rpdo_map.get_item_bytes()
        return bytes(output)
