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
    from ingenialink.dictionary import CanOpenObject, Dictionary

BIT_ENDIAN: Literal["little"] = "little"
bitarray._set_default_endian(BIT_ENDIAN)

PADDING_REGISTER_IDENTIFIER = "PADDING"

MAP_REGISTER_BYTES = 4
"""Number of bytes used to store each mapping register information."""

PDO_MAP_ITEM_TYPE = TypeVar("PDO_MAP_ITEM_TYPE", bound="PDOMapItem")


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

    def __init__(self, is_dirty: bool = True) -> None:
        self.__items: list[PDOMapItem] = []
        self.__map_register_index: Optional[int] = None
        self.__map_object: Optional[CanOpenObject] = None
        self.__slave: Optional[PDOServo] = None
        self.__is_dirty = is_dirty

        # Observer callback
        self._observer_callback: Optional[Callable[[], None]] = None

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

    def subscribe_to_process_data_event(self, callback: Callable[[], None]) -> None:
        """Subscribe to process data notifications.

        Args:
            callback: Subscribed callback function.

        Raises:
            ValueError: If a callback has already been set.
        """
        if self._observer_callback is not None:
            raise ValueError("Callback has already been set, unsubscribe first")
        self._observer_callback = callback

    def unsubscribe_to_process_data_event(self) -> None:
        """Unsubscribe from process data notifications."""
        self._observer_callback = None

    def _notify_process_data_event(self) -> None:
        """Notify the observers about the process data event."""
        if self._observer_callback is not None:
            self._observer_callback()

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

    @staticmethod
    def create_item_from_register_uid(
        uid: str,
        dictionary: "Dictionary",
        axis: Optional[int] = None,
        value: Optional[Union[int, float]] = None,
    ) -> Union[RPDOMapItem, TPDOMapItem]:
        """Create a PDOMapItem from a register uid.

        Args:
            uid: register uid to be mapped.
            dictionary: servo dictionary to retrieve the registers.
            axis: servo axis. Defaults to None.
                Should be specified if multiaxis, None otherwise.
            value: Initial value for an RPDO register.

        Returns:
            PDOMapItem instance.

        Raises:
            ValueError: If there is a type mismatch retrieving the register object.
            ValueError: if the pdo access type is not supported.
            AttributeError: If an initial value is not provided for an RPDO register.
        """
        # Retrieve the register from the dictionary using the uid
        register = dictionary.get_register(uid, axis)
        if not isinstance(register, (EthercatRegister, CanopenRegister)):
            raise ValueError("Expected register type to be EthercatRegister or CanopenRegister.")
        if register.pdo_access == RegCyclicType.RX:
            pdo_map_item = RPDOMapItem(register)
            if value is None:
                raise AttributeError("A initial value is required for a RPDO.")
            pdo_map_item.value = value
            return pdo_map_item
        elif register.pdo_access == RegCyclicType.TX:
            return TPDOMapItem(register)
        raise ValueError(f"Unexpected PDO access type: {register.pdo_access}")

    def add_item(self, item: PDOMapItem) -> None:
        """Append a new item.

        WARNING: This operation can not be done if the servo is not in pre-operational state.

        Args:
            item: Item to be added.

        Raises:
            ValueError: If the item is not of the expected type.
        """
        self.__check_servo_is_in_preoperational_state()
        if not isinstance(item, self._PDO_MAP_ITEM_CLASS):
            raise ValueError(
                f"Expected {self._PDO_MAP_ITEM_CLASS}, got {type(item)}. "
                "Cannot add item to the map."
            )
        self.__is_dirty = True
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
        self.__is_dirty = True
        if not isinstance(registers, list):
            registers = [registers]
        for register in registers:
            item = self.create_item(register)
            self.add_item(item)

    def clear(self) -> None:
        """Clear all items."""
        self.__check_servo_is_in_preoperational_state()
        self.__is_dirty = True
        self.__items.clear()

    def __getitem__(self, index: int) -> PDOMapItem:
        """Get item by index.

        Args:
            index: Index of the item.

        Returns:
            Item at the given index.

        Raises:
            IndexError: If the index is out of range.
        """
        return self.__items.__getitem__(index)

    def __setitem__(self, index: int, item: PDOMapItem) -> None:
        """Set item at the given index.

        Args:
            index: Index of the item.
            item: Item to be set.

        Raises:
            IndexError: If the index is out of range.
            ValueError: If the item is not of the expected type.
        """
        self.__check_servo_is_in_preoperational_state()
        if not isinstance(item, self._PDO_MAP_ITEM_CLASS):
            raise ValueError(
                f"Expected {self._PDO_MAP_ITEM_CLASS}, got {type(item)}. "
                "Cannot set item to the map."
            )
        self.__is_dirty = True
        self.__setitem__(index, item)

    def __delitem__(self, index: int) -> None:
        """Delete item at the given index.

        Args:
            index: Index of the item.

        Raises:
            IndexError: If the index is out of range.
        """
        self.__check_servo_is_in_preoperational_state()
        self.__is_dirty = True
        self.__items.__delitem__(index)

    def __contains__(self, item: PDOMapItem) -> bool:
        """Check if the item is in the PDOMap.

        Args:
            item: Item to be checked.

        Returns:
            True if the item is in the PDOMap, False otherwise.
        """
        return self.__items.__contains__(item)

    @property
    def items(self) -> tuple[PDOMapItem, ...]:
        """Tuple of items (immutable).

        Returns:
            Tuple of items.
        """
        return tuple(self.__items)

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
        if self.map_object is not None and self.map_object.idx != index:
            raise ValueError(
                "The map_object index does not match the map_register_index. "
                f"Expected {self.map_object.idx}, got {index}."
            )

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
        is_dirty: bool,
    ) -> PDO_MAP_TYPE:
        """Create a PDOMap from the full pdo value (accessed via complete access).

        Args:
            value: Value of the pdo mapping in bytes.
            map_obj: Mapping Canopen object.
            dictionary: Canopen dictionary to retrieve the registers.
            is_dirty: If the map has been modified since last read and not written to the slave.

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

        pdo_map.__is_dirty = is_dirty

        return pdo_map

    @classmethod
    def from_pdo_items(
        cls: type[PDO_MAP_TYPE], items: Union[PDO_MAP_ITEM_TYPE, list[PDO_MAP_ITEM_TYPE]]
    ) -> PDO_MAP_TYPE:
        """Create a PDOMap from a list of PDOMapItems.

        Args:
            items: List of PDOMapItems.
            dictionary: Canopen dictionary to retrieve the registers.

        Returns:
            PDOMap instance.

        Raises:
            ValueError: If the items are not of the expected type.
        """
        pdo_map = cls()
        if not isinstance(items, list):
            items = [items]
        for item in items:
            if not isinstance(item, cls._PDO_MAP_ITEM_CLASS):
                raise ValueError(f"Expected item to be of type {cls._PDO_MAP_ITEM_CLASS}.")
            pdo_map.add_item(item)
        return pdo_map

    @property
    def is_editable(self) -> bool:
        """Check if the PDOMap is editable.

        Raises:
            ValueError: If the map_object is None.
                The map_object must be set to check if the map is editable.

        Returns:
            bool: True if the PDOMap is editable, False otherwise.
        """
        if self.map_object is None:
            raise ValueError("The map_object must be set to check if the map is editable")

        return self.map_object.registers[0].access.allows_write

    @property
    def is_dirty(self) -> bool:
        """Check if the PDOMap has been modified since last read and not written to the slave.

        Returns:
            bool: True if the PDOMap is dirty, False otherwise.
        """
        return self.__is_dirty

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
        self.__is_dirty = False

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

    ETG_COMMS_TPDO_ASSIGN_TOTAL = "ETG_COMMS_TPDO_ASSIGN_TOTAL"
    ETG_COMMS_TPDO_ASSIGN_1 = "ETG_COMMS_TPDO_ASSIGN_1"

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
        # Index of the pdo map -> PDO Map instance
        self._rpdo_maps: dict[int, RPDOMap] = {}
        self._tpdo_maps: dict[int, TPDOMap] = {}

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
        self._rpdo_maps.clear()

    def reset_tpdo_mapping(self) -> None:
        """Delete the TPDO mapping stored in the servo slave.

        WARNING: This operation can not be done if the servo is not in pre-operational state.
        """
        self.check_servo_is_in_preoperational_state()
        self.write(self.ETG_COMMS_TPDO_ASSIGN_TOTAL, 0, subnode=0)
        self._tpdo_maps.clear()

    def map_rpdos(self) -> None:
        """Map the RPDO registers into the servo slave.

        It writes the RPDO maps into the slave,
        saves the RPDO maps in the _rpdo_maps attribute
        and adds them to the PDO Assign object.

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
        rpdo_assigns = b""
        for rpdo_map in self._rpdo_maps.values():
            if rpdo_map.is_editable and rpdo_map.is_dirty:
                rpdo_map.write_to_slave()
            rpdo_assigns += rpdo_map.map_register_index_bytes
        self.write_complete_access(self.ETG_COMMS_RPDO_ASSIGN_1, rpdo_assigns, subnode=0)

    def map_tpdos(self) -> None:
        """Map the TPDO registers into the servo slave.

        It writes the TPDO maps into the slave,
        saves the TPDO maps in the _tpdo_maps attribute
        and adds them to the PDO Assign object

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
        tpdo_assigns = b""
        for tpdo_map in self._tpdo_maps.values():
            if tpdo_map.is_editable and tpdo_map.is_dirty:
                tpdo_map.write_to_slave()
            tpdo_assigns += tpdo_map.map_register_index_bytes
        self.write_complete_access(self.ETG_COMMS_TPDO_ASSIGN_1, tpdo_assigns, subnode=0)

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
            rpdo_map_index: The map index of the RPDOMap list to be removed.

        Raises:
            ValueError: If the RPDOMap instance is not in the RPDOMap list.
        """
        self.check_servo_is_in_preoperational_state()
        if rpdo_map_index is None and rpdo_map is None:
            raise ValueError("The RPDOMap instance or the map index should be provided.")
        if rpdo_map is not None:
            if rpdo_map not in self._rpdo_maps.values():
                raise ValueError("The RPDOMap instance is not in the RPDOMaps")
            self._rpdo_maps = {
                idx: rmap for idx, rmap in self._rpdo_maps.items() if rmap is not rpdo_map
            }
            return
        if rpdo_map_index is not None:
            del self._rpdo_maps[rpdo_map_index]

    def remove_tpdo_map(
        self, tpdo_map: Optional[TPDOMap] = None, tpdo_map_index: Optional[int] = None
    ) -> None:
        """Remove a TPDOMap from the TPDOMap list.

        Args:
            tpdo_map: The TPDOMap instance to be removed.
            tpdo_map_index: The map index of the TPDOMap list to be removed.

        Raises:
            ValueError: If the TPDOMap instance is not in the TPDOMap list.

        """
        if tpdo_map_index is None and tpdo_map is None:
            raise ValueError("The TPDOMap instance or the map index should be provided.")
        if tpdo_map is not None:
            if tpdo_map not in self._tpdo_maps.values():
                raise ValueError("The TPDOMap instance is not in the TPDOMaps")
            self._tpdo_maps = {
                idx: tmap for idx, tmap in self._tpdo_maps.items() if tmap is not tpdo_map
            }
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
        for idx in sorted(self._tpdo_maps):
            tpdo_map = self._tpdo_maps[idx]
            map_bytes = input_data[: tpdo_map.data_length_bytes]
            tpdo_map.set_item_bytes(map_bytes)
            input_data = input_data[tpdo_map.data_length_bytes :]
            tpdo_map._notify_process_data_event()

    def _process_rpdo(self) -> bytes:
        """Retrieve the RPDO raw data from each map.

        Returns:
            Concatenated data bytes to be sent.
        """
        output = bytearray()
        for idx in sorted(self._rpdo_maps):
            self._rpdo_maps[idx]._notify_process_data_event()
            output += self._rpdo_maps[idx].get_item_bytes()
        return bytes(output)
