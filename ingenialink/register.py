from abc import ABC
from typing import Any, Dict, List, Optional, Tuple, Union

from ingenialink import exceptions as exc
from ingenialink.enums.register import REG_ACCESS, REG_ADDRESS_TYPE, REG_DTYPE, REG_PHY

# CANOPEN DTYPES
IL_REG_DTYPE_DOMAIN = 15

dtypes_ranges: Dict[REG_DTYPE, Dict[str, Union[int, float]]] = {
    REG_DTYPE.U8: {"max": 255, "min": 0},
    REG_DTYPE.S8: {"max": 127, "min": -128},
    REG_DTYPE.U16: {"max": 65535, "min": 0},
    REG_DTYPE.S16: {"max": 32767, "min": -32767 - 1},
    REG_DTYPE.U32: {"max": 4294967295, "min": 0},
    REG_DTYPE.S32: {"max": 2147483647, "min": -2147483647 - 1},
    REG_DTYPE.U64: {"max": 18446744073709551615, "min": 0},
    REG_DTYPE.S64: {"max": 9223372036854775807, "min": 9223372036854775807 - 1},
    REG_DTYPE.FLOAT: {"max": 3.4e38, "min": -3.4e38},
}


class Register(ABC):
    """Register Base class.

    Args:
        dtype: Data type.
        access: Access type.
        identifier: Identifier.
        units: Units.
        cyclic: Cyclic typed register.
        phy: Physical units.
        subnode: Subnode.
        storage: Storage.
        reg_range: Range (min, max).
        labels: Register labels.
        enums: Enumeration registers.
        cat_id: Category ID.
        scat_id: Sub-category ID.
        internal_use: Internal use.
        address_type: Address tpye.

    Raises:
        TypeError: If any of the parameters has invalid type.
        ILValueError: If the register is invalid.
        ILAccessError: Register with wrong access type.

    """

    def __init__(
        self,
        dtype: REG_DTYPE,
        access: REG_ACCESS,
        identifier: Optional[str] = None,
        units: Optional[str] = None,
        cyclic: str = "CONFIG",
        phy: REG_PHY = REG_PHY.NONE,
        subnode: int = 1,
        storage: Any = None,
        reg_range: Union[
            Tuple[None, None], Tuple[int, int], Tuple[float, float], Tuple[str, str]
        ] = (None, None),
        labels: Optional[Dict[str, str]] = None,
        enums: Optional[Dict[str, int]] = None,
        cat_id: Optional[str] = None,
        scat_id: Optional[str] = None,
        internal_use: int = 0,
        address_type: Optional[REG_ADDRESS_TYPE] = None,
    ) -> None:
        if labels is None:
            labels = {}
        if enums is None:
            enums = {}

        self.__type_errors(dtype, access, phy)

        self._dtype = dtype.value
        self._access = access.value
        self._identifier = identifier
        self._units = units
        self._cyclic = cyclic
        self._phy = phy.value
        self._subnode = subnode
        self._storage = storage
        self._range = (None, None) if not reg_range else reg_range
        self._labels = labels
        self._cat_id = cat_id
        self._scat_id = scat_id
        self._internal_use = internal_use
        self._storage_valid = False if not storage else True
        self._address_type = address_type
        self._enums = enums
        self.__config_range(reg_range)

    def __type_errors(self, dtype: REG_DTYPE, access: REG_ACCESS, phy: REG_PHY) -> None:
        if not isinstance(dtype, REG_DTYPE):
            raise exc.ILValueError("Invalid data type")

        if not isinstance(access, REG_ACCESS):
            raise exc.ILAccessError("Invalid access type")

        if not isinstance(phy, REG_PHY):
            raise exc.ILValueError("Invalid physical units type")

    def __config_range(
        self,
        reg_range: Union[Tuple[None, None], Tuple[int, int], Tuple[float, float], Tuple[str, str]],
    ) -> None:
        if self.dtype in dtypes_ranges:
            if self.dtype == REG_DTYPE.FLOAT:
                if self.storage:
                    self._storage = float(self.storage)
                aux_range = (
                    float(reg_range[0]) if reg_range[0] else dtypes_ranges[self.dtype]["min"],
                    float(reg_range[1]) if reg_range[1] else dtypes_ranges[self.dtype]["max"],
                )
            else:
                if self.storage:
                    self._storage = int(self.storage)
                aux_range = (
                    int(reg_range[0]) if reg_range[0] else dtypes_ranges[self.dtype]["min"],
                    int(reg_range[1]) if reg_range[1] else dtypes_ranges[self.dtype]["max"],
                )
            self._range = aux_range
        else:
            self._storage_valid = False

    @property
    def dtype(self) -> REG_DTYPE:
        """Data type of the register."""
        return REG_DTYPE(self._dtype)

    @property
    def access(self) -> REG_ACCESS:
        """Access type of the register."""
        return REG_ACCESS(self._access)

    @property
    def identifier(self) -> Optional[str]:
        """Register identifier."""
        return self._identifier

    @property
    def units(self) -> Optional[str]:
        """Units of the register."""
        return self._units

    @property
    def cyclic(self) -> str:
        """Defines if the register is cyclic."""
        return self._cyclic

    @property
    def phy(self) -> REG_PHY:
        """Physical units of the register."""
        return REG_PHY(self._phy)

    @property
    def subnode(self) -> int:
        """Target subnode of the register."""
        return self._subnode

    @property
    def storage(self) -> Any:
        """Defines if the register needs to be stored."""
        if not self.storage_valid:
            return None

        if self.dtype in [
            REG_DTYPE.S8,
            REG_DTYPE.U8,
            REG_DTYPE.S16,
            REG_DTYPE.U16,
            REG_DTYPE.S32,
            REG_DTYPE.U32,
            REG_DTYPE.S64,
            REG_DTYPE.U64,
            REG_DTYPE.FLOAT,
        ]:
            return self._storage
        else:
            return None

    @storage.setter
    def storage(self, value: Any) -> None:
        """Defines if the register needs to be stored."""
        self._storage = value

    @property
    def storage_valid(self) -> bool:
        """Defines if the register storage is valid."""
        return self._storage_valid

    @storage_valid.setter
    def storage_valid(self, value: bool) -> None:
        """Defines if the register storage is valid."""
        self._storage_valid = value

    @property
    def range(
        self,
    ) -> Union[Tuple[None, None], Tuple[int, int], Tuple[float, float], Tuple[str, str]]:
        """tuple: Containing the minimum and the maximum values of the register."""
        if self._range:
            return self._range
        return (None, None)

    @property
    def labels(self) -> Dict[str, str]:
        """Containing the labels of the register."""
        return self._labels

    @property
    def enums(self) -> Dict[str, int]:
        """Containing all the enums for the register."""
        return self._enums

    @property
    def enums_count(self) -> int:
        """The number of the enums in the register."""
        return len(self._enums)

    @property
    def cat_id(self) -> Optional[str]:
        """Category ID"""
        return self._cat_id

    @property
    def scat_id(self) -> Optional[str]:
        """Sub-Category ID"""
        return self._scat_id

    @property
    def internal_use(self) -> int:
        """Defines if the register is only for internal uses."""
        return self._internal_use

    @property
    def address_type(self) -> Optional[REG_ADDRESS_TYPE]:
        """Address type of the register."""
        return REG_ADDRESS_TYPE(self._address_type)

    @property
    def mapped_address(self) -> int:
        """Register mapped address used for monitoring/disturbance."""
        raise NotImplementedError()
