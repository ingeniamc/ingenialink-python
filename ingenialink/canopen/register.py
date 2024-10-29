from typing import Any, Dict, Optional, Tuple, Union

from ingenialink.enums.register import (
    REG_ACCESS,
    REG_ADDRESS_TYPE,
    REG_DTYPE,
    REG_PHY,
    RegCyclicType,
)
from ingenialink.register import Register


class CanopenRegister(Register):
    """CANopen Register.

    Args:
        idx: Index of the register.
        subidx: Subindex of the register.
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
        address_type: Address Type.
        description: Register description.
        default: Register default value.

    Raises:
        TypeError: If any of the parameters has invalid type.
        ILValueError: If the register is invalid.
        ILAccessError: Register with wrong access type.

    """

    def __init__(
        self,
        idx: int,
        subidx: int,
        dtype: REG_DTYPE,
        access: REG_ACCESS,
        identifier: Optional[str] = None,
        units: Optional[str] = None,
        cyclic: RegCyclicType = RegCyclicType.CONFIG,
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
        description: Optional[str] = None,
        default: Optional[bytes] = None,
        is_node_id_dependent: bool = False,
    ):
        super().__init__(
            dtype,
            access,
            identifier,
            units,
            cyclic,
            phy,
            subnode,
            storage,
            reg_range,
            labels,
            enums,
            cat_id,
            scat_id,
            internal_use,
            address_type,
            description,
            default,
        )

        self.__idx = idx
        self.__subidx = subidx
        self.__is_node_id_dependent = is_node_id_dependent

    @property
    def idx(self) -> int:
        """Register index."""
        return self.__idx

    @property
    def subidx(self) -> int:
        """Register subindex."""
        return self.__subidx

    @property
    def mapped_address(self) -> int:
        """Register mapped address used for monitoring/disturbance."""
        return self.idx

    @property
    def is_node_id_dependent(self) -> bool:
        """True if register values depends on Node Id"""
        return self.__is_node_id_dependent
