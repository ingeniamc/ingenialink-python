from ingenialink.register import Register
from ingenialink.enums.register import REG_DTYPE, REG_ACCESS, REG_PHY, REG_ADDRESS_TYPE


class CanopenRegister(Register):
    """CANopen Register.

    Args:
        idx (int): Index of the register.
        subidx (int): Subindex of the register.
        dtype (REG_DTYPE): Data type.
        access (REG_ACCESS): Access type.
        identifier (str): Identifier.
        units (str): Units.
        cyclic (str): Cyclic typed register.
        phy (REG_PHY, optional): Physical units.
        subnode (int): Subnode.
        storage (any, optional): Storage.
        reg_range (tuple, optional): Range (min, max).
        labels (dict, optional): Register labels.
        enums (dict): Enumeration registers.
        enums_count (int): Number of enumeration registers.
        cat_id (str, optional): Category ID.
        scat_id (str, optional): Sub-category ID.
        internal_use (int, optional): Internal use.
        address_type (REG_ADDRESS_TYPE): Address Type.

    Raises:
        TypeError: If any of the parameters has invalid type.
        ILValueError: If the register is invalid.
        ILAccessError: Register with wrong access type.

    """

    def __init__(
        self,
        idx,
        subidx,
        dtype,
        access,
        identifier=None,
        units=None,
        cyclic="CONFIG",
        phy=REG_PHY.NONE,
        subnode=1,
        storage=None,
        reg_range=(None, None),
        labels=None,
        enums=None,
        cat_id=None,
        scat_id=None,
        internal_use=0,
        address_type=None,
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

        self.__idx = idx
        self.__subidx = subidx

    @property
    def idx(self):
        """int: Register index."""
        return self.__idx

    @property
    def subidx(self):
        """int: Register subindex."""
        return self.__subidx

    @property
    def mapped_address(self):
        """int: Register mapped address used for monitoring/disturbance."""
        return self.idx
