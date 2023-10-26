from typing import Optional, Any, Union, Tuple, Dict, List

from ingenialink.canopen.register import CanopenRegister
from ingenialink.enums.register import REG_DTYPE, REG_ACCESS, REG_PHY, REG_ADDRESS_TYPE


class EthercatRegister(CanopenRegister):
    """EtherCAT Register.

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
            idx,
            subidx,
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
