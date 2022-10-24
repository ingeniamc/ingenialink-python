from ingenialink.register import Register
from ingenialink.enums.register import REG_DTYPE, REG_ACCESS, REG_PHY


class CanopenRegister(Register):
    """CANopen Register.

        Args:
            identifier (str): Identifier.
            units (str): Units.
            cyclic (str): Cyclic typed register.
            idx (int): Index of the register.
            subidx (int): Subindex of the register.
            dtype (REG_DTYPE): Data type.
            access (REG_ACCESS): Access type.
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

    def __init__(self, identifier, units, cyclic, idx, subidx, dtype,
                 access, phy=REG_PHY.NONE, subnode=1, storage=None,
                 reg_range=(None, None), labels=None, enums=None, enums_count=0,
                 cat_id=None, scat_id=None, internal_use=0):

        super().__init__(dtype, access, identifier, units, cyclic,
                         phy, subnode, storage, reg_range, labels, enums,
                         enums_count, cat_id, scat_id, internal_use)

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
