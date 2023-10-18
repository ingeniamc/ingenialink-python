from typing import Optional, Union, Tuple, Any, Dict, List

from ingenialink.register import Register
from ingenialink.enums.register import REG_DTYPE, REG_ACCESS, REG_PHY, REG_ADDRESS_TYPE


class EthernetRegister(Register):
    """Ethernet Register.

    Args:
        address (int): Address of the register.
        dtype (REG_DTYPE): Data type.
        access (REG_ACCESS): Access type.
        identifier (str, optional): Identifier.
        units (str, optional): Units.
        cyclic (str, optional): Cyclic typed register.
        phy (REG_PHY, optional): Physical units.
        subnode (int): Subnode.
        storage (any, optional): Storage.
        reg_range (tuple, optional): Range (min, max).
        labels (dict, optional): Register labels.
        enums (dict): Enumeration registers.
        cat_id (str, optional): Category ID.
        scat_id (str, optional): Sub-category ID.
        internal_use (int, optional): Internal use.
        address_type (REG_ADDRESS_TYPE): Address Type.

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
        enums: Optional[List[Dict[str, Union[str, int]]]] = None,
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
        """int: Register address."""
        return self.__address

    @property
    def mapped_address(self) -> int:
        """int: Register mapped address used for monitoring/disturbance."""
        address_offset = self.MAP_ADDRESS_OFFSET * (self.subnode - 1)
        return self.address + address_offset
