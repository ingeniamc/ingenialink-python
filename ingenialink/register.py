from abc import ABC
from dataclasses import dataclass
from typing import Any, Optional, Union

from ingenialink import exceptions as exc
from ingenialink.bitfield import BitField
from ingenialink.enums.register import (
    RegAccess,
    RegAddressType,
    RegCyclicType,
    RegDtype,
    RegPhy,
)
from ingenialink.utils._utils import convert_bytes_to_dtype, dtype_length_bits

dtypes_ranges: dict[RegDtype, dict[str, Union[int, float]]] = {
    RegDtype.U8: {"max": 255, "min": 0},
    RegDtype.S8: {"max": 127, "min": -128},
    RegDtype.U16: {"max": 65535, "min": 0},
    RegDtype.S16: {"max": 32767, "min": -32767 - 1},
    RegDtype.U32: {"max": 4294967295, "min": 0},
    RegDtype.S32: {"max": 2147483647, "min": -2147483647 - 1},
    RegDtype.U64: {"max": 18446744073709551615, "min": 0},
    RegDtype.S64: {"max": 9223372036854775807, "min": 9223372036854775807 - 1},
    RegDtype.FLOAT: {"max": 3.4e38, "min": -3.4e38},
}


@dataclass(frozen=True)
class MonDistV3:
    """Monitoring data."""

    address: int
    subnode: int
    cyclic: RegCyclicType


class Register(ABC):
    """Register Base class.

    Args:
        dtype: Data type.
        access: Access type.
        identifier: Identifier.
        units: Units.
        pdo_access: pdo access.
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
        description: Register description.
        default: Register default value.
        bitfields: Fields that specify groups of bits.
        monitoring: monitoring information (address, subnode, cyclic access),
            None if register is not monitoreable.

    Raises:
        TypeError: If any of the parameters has invalid type.
        ILValueError: If the register is invalid.
        ILAccessError: Register with wrong access type.

    """

    def __init__(
        self,
        dtype: RegDtype,
        access: RegAccess,
        identifier: Optional[str] = None,
        units: Optional[str] = None,
        pdo_access: RegCyclicType = RegCyclicType.CONFIG,
        phy: RegPhy = RegPhy.NONE,
        subnode: int = 1,
        storage: Any = None,
        reg_range: Union[
            tuple[None, None], tuple[int, int], tuple[float, float], tuple[str, str]
        ] = (None, None),
        labels: Optional[dict[str, str]] = None,
        enums: Optional[dict[str, int]] = None,
        cat_id: Optional[str] = None,
        scat_id: Optional[str] = None,
        internal_use: int = 0,
        address_type: Optional[RegAddressType] = RegAddressType.NVM_NONE,
        description: Optional[str] = None,
        default: Optional[bytes] = None,
        bitfields: Optional[dict[str, BitField]] = None,
        monitoring: Optional[MonDistV3] = None,
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
        self._pdo_access = pdo_access
        self._phy = phy.value
        self._subnode = subnode
        self._storage = storage
        self._range = reg_range if reg_range else (None, None)
        self._labels = labels
        self._cat_id = cat_id
        self._scat_id = scat_id
        self._internal_use = internal_use
        self._storage_valid = storage is not None
        self._address_type = address_type
        self._description = description
        self._default = default
        self._enums = enums
        self.__bitfields = bitfields
        self._monitoring = monitoring
        self.__config_range(reg_range)

    def __type_errors(self, dtype: RegDtype, access: RegAccess, phy: RegPhy) -> None:
        if not isinstance(dtype, RegDtype):
            raise exc.ILValueError("Invalid data type")

        if not isinstance(access, RegAccess):
            raise exc.ILAccessError("Invalid access type")

        if not isinstance(phy, RegPhy):
            raise exc.ILValueError("Invalid physical units type")

    def __config_range(
        self,
        reg_range: Union[tuple[None, None], tuple[int, int], tuple[float, float], tuple[str, str]],
    ) -> None:
        cast_type: Union[type[int], type[float]]
        if self.dtype not in dtypes_ranges:
            self._storage_valid = False
            return
        elif self.dtype == RegDtype.FLOAT:
            cast_type = float
        else:
            cast_type = int
        reg_range_min = (
            cast_type(reg_range[0])
            if reg_range[0] is not None
            else dtypes_ranges[self.dtype]["min"]
        )
        reg_range_max = (
            cast_type(reg_range[1])
            if reg_range[1] is not None
            else dtypes_ranges[self.dtype]["max"]
        )
        self._range = reg_range_min, reg_range_max
        if self.storage is not None:
            self._storage = cast_type(self.storage)

    @property
    def dtype(self) -> RegDtype:
        """Data type of the register."""
        return RegDtype(self._dtype)

    @property
    def access(self) -> RegAccess:
        """Access type of the register."""
        return RegAccess(self._access)

    @property
    def identifier(self) -> Optional[str]:
        """Register identifier."""
        return self._identifier

    @property
    def units(self) -> Optional[str]:
        """Units of the register."""
        return self._units

    @property
    def pdo_access(self) -> RegCyclicType:
        """Defines if the register is pdo mappable."""
        return self._pdo_access

    @property
    def phy(self) -> RegPhy:
        """Physical units of the register."""
        return RegPhy(self._phy)

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
            RegDtype.S8,
            RegDtype.U8,
            RegDtype.S16,
            RegDtype.U16,
            RegDtype.S32,
            RegDtype.U32,
            RegDtype.S64,
            RegDtype.U64,
            RegDtype.FLOAT,
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
    ) -> Union[tuple[None, None], tuple[int, int], tuple[float, float], tuple[str, str]]:
        """tuple: Containing the minimum and the maximum values of the register."""
        if self._range:
            return self._range
        return (None, None)

    @property
    def monitoring(self) -> Optional[MonDistV3]:
        """Containing the address, subnode and cyclic access.

        If the register is not monitoreable, it will contain None.
        """
        return self._monitoring

    @property
    def labels(self) -> dict[str, str]:
        """Containing the labels of the register."""
        return self._labels

    @property
    def enums(self) -> dict[str, int]:
        """Containing all the enums for the register."""
        return self._enums

    @property
    def enums_count(self) -> int:
        """The number of the enums in the register."""
        return len(self._enums)

    @property
    def cat_id(self) -> Optional[str]:
        """Category ID."""
        return self._cat_id

    @cat_id.setter
    def cat_id(self, category: str) -> None:
        """Category ID."""
        self._cat_id = category

    @property
    def scat_id(self) -> Optional[str]:
        """Sub-Category ID."""
        return self._scat_id

    @property
    def internal_use(self) -> int:
        """Defines if the register is only for internal uses."""
        return self._internal_use

    @property
    def address_type(self) -> Optional[RegAddressType]:
        """Address type of the register."""
        return RegAddressType(self._address_type)

    @property
    def description(self) -> Optional[str]:
        """Register description."""
        return self._description

    @property
    def default(self) -> Union[None, int, float, str, bytes]:
        """Register default value."""
        if self._default is None:
            return self._default
        return convert_bytes_to_dtype(self._default, self.dtype)

    @property
    def mapped_address(self) -> int:
        """Register mapped address used for monitoring/disturbance."""
        raise NotImplementedError

    @property
    def bitfields(self) -> Optional[dict[str, BitField]]:
        """Register bit fields."""
        return self.__bitfields

    @property
    def bit_length(self) -> int:
        """Get the bit length of the register.

        Returns:
            int: bit length of the register.
        """
        return dtype_length_bits[self.dtype]

    def __repr__(self) -> str:
        """String representation of the Register class.

        Returns:
            str: String representation of the Register instance.
        """
        return f"<{self.__class__.__name__} {self.identifier} at 0x{id(self):X} >"
