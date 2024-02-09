from typing import List, Optional, Union

from bitarray import bitarray, bits2bytes

from ingenialink.canopen.register import CanopenRegister
from ingenialink.enums.register import REG_DTYPE
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.exceptions import ILError
from ingenialink.servo import Servo
from ingenialink.utils._utils import (
    convert_bytes_to_dtype,
    convert_dtype_to_bytes,
    dtype_length_bits,
)


class PDOMapItem:
    """Abstract class to represent a register in the PDO mapping.

    Attributes:
        register: mapped register object.
        size_bits: custom register size in bits.

    """

    ACCEPTED_CYCLIC = ""
    """Accepted cyclic: CYCLIC_TX or CYCLIC_RX."""

    def __init__(
        self, register: Union[EthercatRegister, CanopenRegister], size_bits: Optional[int] = None
    ) -> None:
        self.register = register
        self.size_bits = size_bits or dtype_length_bits[register.dtype]
        self._raw_data_bits: Optional[bitarray] = None
        self._check_if_mappable()

    def _check_if_mappable(self) -> None:
        """Check if the passed register is mappable. I.e., if the cyclic information is correct.

        Raises:
            ILError: Tf the register is not mappable.
        """
        if not self.register.cyclic == self.ACCEPTED_CYCLIC:
            raise ILError(
                f"Incorrect cyclic. It should be {self.ACCEPTED_CYCLIC}, obtained:"
                f" {self.register.cyclic}"
            )

    @property
    def raw_data_bits(self) -> bitarray:
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
    def raw_data_bits(self, data: bitarray) -> None:
        if len(data) != self.size_bits:
            raise ILError(f"Wrong size. Expected {self.size_bits}, obtained {len(data)}")
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
        data_bits = bitarray()
        data_bits.frombytes(data)
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

    ACCEPTED_CYCLIC = "CYCLIC_RX"

    def __init__(
        self, register: Union[EthercatRegister, CanopenRegister], size_bits: Optional[int] = None
    ) -> None:
        super().__init__(register, size_bits)

    @property
    def value(self) -> Union[int, float]:
        return super().value

    @value.setter
    def value(self, value: Union[int, float, bool]) -> None:
        if isinstance(value, bool):
            raw_data_bits = bitarray()
            raw_data_bits.append(value)
            self.raw_data_bits = raw_data_bits
        else:
            raw_data_bytes = convert_dtype_to_bytes(value, self.register.dtype)
            self.raw_data_bytes = raw_data_bytes


class TPDOMapItem(PDOMapItem):
    """Class to represent TPDO mapping items."""

    ACCEPTED_CYCLIC = "CYCLIC_TX"


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
        """Index of the mapping register. None if it is not mapped in the drive.

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
        length = 0
        for item in self.items:
            length += item.size_bits
        return length

    @property
    def data_length_bytes(self) -> int:
        """Length of the map in bytes.

        Returns:
            Length of the map in bytes.
        """
        return bits2bytes(self.data_length_bits)

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


class RPDOMap(PDOMap):
    """Class to store RPDO mapping information."""

    _PDO_MAP_ITEM_CLASS = RPDOMapItem

    def get_item_bits(self) -> bitarray:
        """Return the concatenated items raw data to be sent to the drive (in bits).

        Raises:
            ILError: Raw data is empty.
            ILError: If the length of the bit array is incorrect.

        Returns:
            Concatenated items raw data in bits.
        """
        data_bits = bitarray()
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
        """Return the concatenated items raw data to be sent to the drive (in bytes).

        Raises:
            ILError: Raw data is empty.
            ILError: If the length of th byte array is incorrect.

        Returns:
            Concatenated items raw data in bytes.
        """
        item_bits = self.get_item_bits()
        return item_bits.tobytes()


class TPDOMap(PDOMap):
    """Class to store TPDO mapping information."""

    _PDO_MAP_ITEM_CLASS = TPDOMapItem

    def set_item_bytes(self, data_bytes: bytes) -> None:
        """Set the items raw data from a byte array received from the drive.

        Args:
            data_bytes: Byte array received from the drive.

        Raises:
            ILError: If the length of the received data does not coincide.
        """
        if len(data_bytes) != self.data_length_bytes:
            raise ILError(
                f"The length of the data array is incorrect. Expected {self.data_length_bytes},"
                f" obtained {len(data_bytes)}"
            )
        data_bits = bitarray()
        data_bits.frombytes(data_bytes)

        offset = 0
        for item in self.items:
            item.raw_data_bits = data_bits[offset : item.size_bits + offset]
            offset += item.size_bits


class PDOServo(Servo):
    """Abstract class to implement PDOs in a Servo class."""

    AVAILABLE_PDOS = 1

    RPDO_ASSIGN_REGISTER_SUB_IDX_0: Union[EthercatRegister, CanopenRegister]
    RPDO_ASSIGN_REGISTER_SUB_IDX_1: Union[EthercatRegister, CanopenRegister]
    RPDO_MAP_REGISTER_SUB_IDX_0: List[Union[EthercatRegister, CanopenRegister]]
    RPDO_MAP_REGISTER_SUB_IDX_1: List[Union[EthercatRegister, CanopenRegister]]

    TPDO_ASSIGN_REGISTER_SUB_IDX_0: Union[EthercatRegister, CanopenRegister]
    TPDO_ASSIGN_REGISTER_SUB_IDX_1: Union[EthercatRegister, CanopenRegister]
    TPDO_MAP_REGISTER_SUB_IDX_0: List[Union[EthercatRegister, CanopenRegister]]
    TPDO_MAP_REGISTER_SUB_IDX_1: List[Union[EthercatRegister, CanopenRegister]]

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
        """Delete the RPDO mapping stored in the servo drive."""
        self.write(self.RPDO_ASSIGN_REGISTER_SUB_IDX_0, 0)
        for map_register in self.RPDO_MAP_REGISTER_SUB_IDX_0:
            self.write(map_register, 0)
        self._rpdo_maps.clear()

    def reset_tpdo_mapping(self) -> None:
        """Delete the TPDO mapping stored in the servo drive."""
        self.write(self.TPDO_ASSIGN_REGISTER_SUB_IDX_0, 0)
        for map_register in self.TPDO_MAP_REGISTER_SUB_IDX_0:
            self.write(map_register, 0)
        self._tpdo_maps.clear()

    def map_rpdos(self) -> None:
        """Map the RPDO registers into the servo drive.
        It takes the first available RPDO assignment slot of the drive.

        Raises:
            ILError: If there are no available PDOs.
        """
        if len(self._rpdo_maps) > self.AVAILABLE_PDOS:
            raise ILError(
                f"Could not map the RPDO maps, received {len(self._rpdo_maps)} PDOs and only"
                f" {self.AVAILABLE_PDOS} are available"
            )
        self.write(self.RPDO_ASSIGN_REGISTER_SUB_IDX_0, len(self._rpdo_maps))
        custom_map_index = 0
        rpdo_assigns = b""
        for rpdo_map in self._rpdo_maps:
            if rpdo_map.map_register_index is None:
                self._set_rpdo_map_register(custom_map_index, rpdo_map)
                custom_map_index += 1
            rpdo_assigns += rpdo_map.map_register_index_bytes
        self.write(
            self.RPDO_ASSIGN_REGISTER_SUB_IDX_1,
            rpdo_assigns,
            complete_access=True,
        )

    def _set_rpdo_map_register(self, rpdo_map_register_index: int, rpdo_map: RPDOMap) -> None:
        """Fill RPDO map register with PRDOMap object data

        Args:
            rpdo_map_register_index: custom rpdo map register index
            rpdo_map: custom rpdo data

        """
        self.write(self.RPDO_MAP_REGISTER_SUB_IDX_0[rpdo_map_register_index], len(rpdo_map.items))
        self.write(
            self.RPDO_MAP_REGISTER_SUB_IDX_1[rpdo_map_register_index],
            rpdo_map.items_mapping.decode("utf-8"),
            complete_access=True,
        )
        rpdo_map.map_register_index = self.RPDO_MAP_REGISTER_SUB_IDX_0[rpdo_map_register_index].idx

    def map_tpdos(self) -> None:
        """Map the TPDO registers into the servo drive.
        It takes the first available TPDO assignment slot of the drive.

        Raises:
            ILError: If there are no available PDOs.
        """
        if len(self._tpdo_maps) > self.AVAILABLE_PDOS:
            raise ILError(
                f"Could not map the TPDO maps, received {len(self._tpdo_maps)} PDOs and only"
                f" {self.AVAILABLE_PDOS} are available"
            )
        self.write(self.TPDO_ASSIGN_REGISTER_SUB_IDX_0, len(self._tpdo_maps))
        custom_map_index = 0
        tpdo_assigns = b""
        for tpdo_map in self._tpdo_maps:
            if tpdo_map.map_register_index is None:
                self._set_tpdo_map_register(custom_map_index, tpdo_map)
                custom_map_index += 1
            tpdo_assigns += tpdo_map.map_register_index_bytes
        self.write(
            self.TPDO_ASSIGN_REGISTER_SUB_IDX_1,
            tpdo_assigns,
            complete_access=True,
        )

    def _set_tpdo_map_register(self, tpdo_map_register_index: int, tpdo_map: TPDOMap) -> None:
        """Fill TPDO map register with TRDOMap object data

        Args:
            tpdo_map_register_index: custom tpdo map register index
            tpdo_map: custom tpdo data

        """
        self.write(self.TPDO_MAP_REGISTER_SUB_IDX_0[tpdo_map_register_index], len(tpdo_map.items))
        self.write(
            self.TPDO_MAP_REGISTER_SUB_IDX_1[tpdo_map_register_index],
            tpdo_map.items_mapping.decode("utf-8"),
            complete_access=True,
        )
        tpdo_map.map_register_index = self.TPDO_MAP_REGISTER_SUB_IDX_0[tpdo_map_register_index].idx

    def map_pdos(self, slave_index: int) -> None:
        """Map RPDO and TPDO register into the drive.

        Args:
            slave_index: salve index.
        """
        self.map_tpdos()
        self.map_rpdos()

    def set_pdo_map_to_slave(self, rpdo_maps: List[RPDOMap], tpdo_maps: List[TPDOMap]) -> None:
        """Callback called by the slave to configure the map.

        Args:
            rpdo_maps: List of RPDO maps.
            tpdo_maps: List of TPDO maps.
        """
        raise NotImplementedError

    def process_pdo_inputs(self) -> None:
        """Process the PDO inputs.

        It should call _process_rpdo method to obtain the bytes to be sent to the drive.
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
