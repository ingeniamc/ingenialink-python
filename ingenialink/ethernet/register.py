from ingenialink.register import Register, REG_DTYPE, REG_ACCESS, REG_PHY


class EthernetRegister(Register):
    """Ethernet Register.

        Args:
            idx (int): Index of the register.
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
            enums (list): Enumeration registers.
            enums_count (int): Number of enumeration registers.
            cat_id (str, optional): Category ID.
            scat_id (str, optional): Sub-category ID.
            internal_use (int, optional): Internal use.

        Raises:
            TypeError: If any of the parameters has invalid type.
            ILValueError: If the register is invalid.
            ILAccessError: Register with wrong access type.

        """

    def __init__(self, address, dtype, access, identifier=None, units=None, cyclic="CONFIG",
                 phy=REG_PHY.NONE, subnode=1, storage=None, reg_range=(None, None),
                 labels=None, enums=None, enums_count=0, cat_id=None, scat_id=None,
                 internal_use=0):

        super().__init__(dtype, access, identifier, units, cyclic, phy, subnode,
                         storage, reg_range, labels, enums, enums_count, cat_id,
                         scat_id, internal_use)

        self.__address = address

    @property
    def address(self):
        """int: Register address."""
        return self.__address
