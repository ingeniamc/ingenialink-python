from typing import List, Optional, Union

from ingenialink.canopen.register import CanopenRegister
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.exceptions import ILError
from ingenialink.servo import Servo
from ingenialink.utils._utils import convert_bytes_to_dtype, convert_dtype_to_bytes, dtype_value


class PDOMapItem:
    """Abstract class to represent a register in the PDO mapping.

    Attributes:
        register: mapped register object.
        size: custom register size.

    """

    ACCEPTED_CYCLIC = ""
    """Accepted cyclic: CYCLIC_TX or CYCLIC_RX."""

    def __init__(
        self, register: Union[EthercatRegister, CanopenRegister], size: Optional[int] = None
    ) -> None:
        self.register = register
        self.size = size or dtype_value[register.dtype][0]
        self._raw_data: Optional[bytes] = None
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
    def raw_data(self) -> bytes:
        """Raw data in bytes.

        Returns:
            Raw data in bytes

        Raises:
            ILError: If the raw data is empty.

        """
        if self._raw_data is None:
            raise ILError("Raw data is empty.")
        return self._raw_data

    @raw_data.setter
    def raw_data(self, data: bytes) -> None:
        self._raw_data = data

    @property
    def value(self) -> Union[int, float]:
        """Register value. Converts the raw data bytes into the register value.

        Raises:
            ILError: If the raw data is empty.
            ILError: If the register type is not int or float.

        Returns:
            Register value.
        """
        value = convert_bytes_to_dtype(self.raw_data, self.register.dtype)
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
        mapped_register = (index << 16) | (self.size * 8)
        mapped_register_bytes: bytes = mapped_register.to_bytes(4, "little")
        return mapped_register_bytes


class RPDOMapItem(PDOMapItem):
    """Class to represent RPDO mapping items."""

    ACCEPTED_CYCLIC = "CYCLIC_RX"

    def __init__(
        self, register: Union[EthercatRegister, CanopenRegister], size: Optional[int] = None
    ) -> None:
        super().__init__(register, size)

    @property
    def value(self) -> Union[int, float]:
        return super().value

    @value.setter
    def value(self, value: Union[int, float]) -> None:
        raw_data = convert_dtype_to_bytes(value, self.register.dtype)
        self.raw_data = raw_data


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
        self, register: Union[EthercatRegister, CanopenRegister], size: Optional[int] = None
    ) -> PDOMapItem:
        """Create a new PDOMapItem.

        Args:
            register: Register object.
            size: Register size.

        Returns:
            PDO Map item.
        """
        item = self._PDO_MAP_ITEM_CLASS(register, size)
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
    def data_bytes_length(self) -> int:
        """Length of the map bytes.

        Returns:
            Length of the map bytes.
        """
        length = 0
        for item in self.items:
            length += item.size
        return length

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

    def get_item_bytes(self) -> bytearray:
        """Return the concatenated items raw data to be sent to the drive.

        Raises:
            ILError: Raw data is empty.
            ILError: If the length of th byte array is incorrect.

        Returns:
            Concatenated items raw data.
        """
        data_bytes = bytearray()
        for item in self.items:
            try:
                data_bytes += item.raw_data
            except ILError:
                raise ILError(f"PDO item {item.register.identifier} does not have data stored.")

        if len(data_bytes) != self.data_bytes_length:
            raise ILError(
                f"The length of the data array is incorrect. Expected {self.data_bytes_length},"
                f" obtained {len(data_bytes)}"
            )
        return data_bytes


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
        if len(data_bytes) != self.data_bytes_length:
            raise ILError(
                f"The length of the data array is incorrect. Expected {self.data_bytes_length},"
                f" obtained {len(data_bytes)}"
            )
        offset = 0
        for item in self.items:
            item.raw_data = data_bytes[offset : item.size + offset]
            offset += item.size


class PDOServo(Servo):
    """Abstract class to implement PDOs in a Servo class."""

    AVAILABLE_PDOS = 1

    RPDO_ASSIGN_REGISTER_SUB_IDX_0: Union[EthercatRegister, CanopenRegister]
    RPDO_ASSIGN_REGISTER_SUB_IDX_1: List[Union[EthercatRegister, CanopenRegister]]
    RPDO_MAP_REGISTER_SUB_IDX_0: List[Union[EthercatRegister, CanopenRegister]]
    RPDO_MAP_REGISTER_SUB_IDX_1: List[Union[EthercatRegister, CanopenRegister]]

    TPDO_ASSIGN_REGISTER_SUB_IDX_0: Union[EthercatRegister, CanopenRegister]
    TPDO_ASSIGN_REGISTER_SUB_IDX_1: List[Union[EthercatRegister, CanopenRegister]]
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

    def add_rpdo_map(self, rpdo_map: RPDOMap) -> None:
        """Add a new RPDO map into the drive.

        It takes the first available (not mapped yet) RPDO assignment slot of the drive.

        Args:
            rpdo_map: RPDO map to be added.

        Raises:
            ILError: If there are no available PDOs.
        """
        if len(self._rpdo_maps) + 1 > self.AVAILABLE_PDOS:
            raise ILError("Could not add a new RPDO map, there are no available PDOs.")
        self._rpdo_maps.append(rpdo_map)
        map_index = len(self._rpdo_maps) - 1

        self.write(self.RPDO_ASSIGN_REGISTER_SUB_IDX_0, len(self._rpdo_maps))
        self.write(self.RPDO_MAP_REGISTER_SUB_IDX_0[map_index], len(rpdo_map.items))
        self.write(
            self.RPDO_MAP_REGISTER_SUB_IDX_1[map_index],
            rpdo_map.items_mapping.decode("utf-8"),
            complete_access=True,
        )
        self.write(
            self.RPDO_ASSIGN_REGISTER_SUB_IDX_1[map_index],
            self.RPDO_MAP_REGISTER_SUB_IDX_0[map_index].idx,
            complete_access=True,
        )
        rpdo_map.map_register_index = self.RPDO_MAP_REGISTER_SUB_IDX_0[map_index].idx

    def add_tpdo_map(self, tpdo_map: TPDOMap) -> None:
        """Add a new TPDO map into the drive.

        It takes the first available (not mapped yet) TPDO assignment slot of the drive.

        Args:
            tpdo_map: TPDO map to be added.

        Raises:
            ILError: If there are no available PDOs.
        """
        if len(self._tpdo_maps) + 1 > self.AVAILABLE_PDOS:
            raise ILError("Could not add a new TPDO map, there are no available PDOs.")
        self._tpdo_maps.append(tpdo_map)
        map_index = len(self._tpdo_maps) - 1

        self.write(self.TPDO_ASSIGN_REGISTER_SUB_IDX_0, len(self._tpdo_maps))
        self.write(self.TPDO_MAP_REGISTER_SUB_IDX_0[map_index], len(tpdo_map.items))
        self.write(
            self.TPDO_MAP_REGISTER_SUB_IDX_1[map_index],
            tpdo_map.items_mapping.decode("utf-8"),
            complete_access=True,
        )
        self.write(
            self.TPDO_ASSIGN_REGISTER_SUB_IDX_1[map_index],
            self.TPDO_MAP_REGISTER_SUB_IDX_0[map_index].idx,
            complete_access=True,
        )
        tpdo_map.map_register_index = self.TPDO_MAP_REGISTER_SUB_IDX_0[map_index].idx

    def map_rpdos(self, rpdo_maps: List[RPDOMap]) -> None:
        """Map the RPDO registers into the servo drive.

        Args:
            rpdo_maps: List of RPDO maps.
        """
        if len(rpdo_maps) > self.AVAILABLE_PDOS:
            raise ILError(
                f"Could not map the RPDO maps, received {len(rpdo_maps)} PDOs and only"
                " {self.AVAILABLE_PDOS} are available"
            )

        self.reset_rpdo_mapping()
        for rpdo_map in rpdo_maps:
            self.add_rpdo_map(rpdo_map)

    def map_tpdos(self, tpdo_maps: List[TPDOMap]) -> None:
        """Map the TPDO registers into the servo drive.

        Args:
            tpdo_maps: List of TPDO maps.
        """
        if len(tpdo_maps) > self.AVAILABLE_PDOS:
            raise ILError(
                f"Could not map the TPDO maps, received {len(tpdo_maps)} PDOs and only"
                f" {self.AVAILABLE_PDOS} are available"
            )

        self.reset_tpdo_mapping()
        for tpdo_map in tpdo_maps:
            self.add_tpdo_map(tpdo_map)

    def map_pdos(self, rpdo_maps: List[RPDOMap], tpdo_maps: List[TPDOMap], *args: int) -> None:
        """Map RPDO and TPDO register into the drive.

        Args:
            rpdo_maps: List of RPDO maps.
            tpdo_maps: List of TPDO maps.
        """
        self.map_tpdos(tpdo_maps)
        self.map_rpdos(rpdo_maps)

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
            map_bytes = input_data[: tpdo_map.data_bytes_length]
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
