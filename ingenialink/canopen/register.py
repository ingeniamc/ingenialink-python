from typing import Any, Optional, Union

from ingenialink.bitfield import BitField
from ingenialink.enums.register import (
    RegAccess,
    RegAddressType,
    RegCyclicType,
    RegDtype,
    RegPhy,
)
from ingenialink.register import MonDistV3, Register


class CanopenRegister(Register):
    """CANopen Register.

    Args:
        idx: Index of the register.
        subidx: Subindex of the register.
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
        address_type: Address Type.
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
        idx: int,
        subidx: int,
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
        is_node_id_dependent: bool = False,
    ):
        super().__init__(
            dtype,
            access,
            identifier,
            units,
            pdo_access,
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
            bitfields,
            monitoring=monitoring,
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
        """True if register values depends on Node Id."""
        return self.__is_node_id_dependent
