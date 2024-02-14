from typing import Any, Dict, List, Optional, Tuple, Union

from ingenialink.enums.register import REG_ACCESS, REG_ADDRESS_TYPE, REG_DTYPE, REG_PHY
from ingenialink.register import Register


class EthernetRegister(Register):
    """Ethernet Register.

    Args:
        address: Address of the register.
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

    Raises:
        TypeError: If any of the parameters has invalid type.
        ILValueError: If the register is invalid.
        ILAccessError: Register with wrong access type.

    """

    MAP_ADDRESS_OFFSET = 0x800

    def __init__(
        self,
        address: int,
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
        )

        self.__address = address

    @property
    def address(self) -> int:
        """Register address."""
        return self.__address

    @property
    def mapped_address(self) -> int:
        """Register mapped address used for monitoring/disturbance."""
        address_offset = self.MAP_ADDRESS_OFFSET * (self.subnode - 1)
        return self.address + address_offset
