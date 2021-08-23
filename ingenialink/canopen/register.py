from .._ingenialink import lib

from ingenialink.utils._utils import *
from ingenialink.register import Register, REG_DTYPE, REG_ACCESS, REG_PHY


class CanopenRegister(Register):
    """CANopen Register.

        Args:
            identifier (str): Identifier.
            units (str): Units.
            cyclic (str): Cyclic typed register.
            idx (str): Index of the register.
            subidx (str): Subindex of the register.
            dtype (REG_DTYPE): Data type.
            access (REG_ACCESS): Access type.
            phy (REG_PHY, optional): Physical units.
            subnode (int): Subnode.
            storage (any, optional): Storage.
            range (tuple, optional): Range (min, max).
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
                 range=(None, None), labels={}, enums=[], enums_count=0,
                 cat_id=None, scat_id=None, internal_use=0):
        super(CanopenRegister, self).__init__(
            identifier, units, cyclic, dtype, access, phy, subnode,
            storage, range, labels, enums, enums_count, cat_id,
            scat_id, internal_use)
        if not isinstance(dtype, REG_DTYPE):
            raise_err(lib.IL_EINVAL, 'Invalid data type')

        if not isinstance(access, REG_ACCESS):
            raise_err(lib.IL_EACCESS, 'Invalid access type')

        if not isinstance(phy, REG_PHY):
            raise_err(lib.IL_EINVAL, 'Invalid physical units type')

        self.__idx = idx
        self.__subidx = subidx

        if dtype == REG_DTYPE.S8:
            if storage:
                self.storage = int(storage)

            range_min = (range[0] if range[0] else INT_SIZES.S8_MIN.value)
            range_max = (range[1] if range[1] else INT_SIZES.S8_MAX.value)
            self.range = (int(range_min), int(range_max))
        elif dtype == REG_DTYPE.U8:
            if storage:
                self.storage = int(storage)

            range_min = range[0] if range[0] else 0
            range_max = (range[1] if range[1] else INT_SIZES.U8_MAX.value)
            self.range = (int(range_min), int(range_max))
        if dtype == REG_DTYPE.S16:
            if storage:
                self.storage = int(storage)

            range_min = (range[0] if range[0] else INT_SIZES.S16_MIN.value)
            range_max = (range[1] if range[1] else INT_SIZES.S16_MAX.value)
            self.range = (int(range_min), int(range_max))
        elif dtype == REG_DTYPE.U16:
            if storage:
                self.storage = int(storage)

            range_min = range[0] if range[0] else 0
            range_max = (range[1] if range[1] else INT_SIZES.U16_MAX.value)
            self.range = (int(range_min), int(range_max))
        if dtype == REG_DTYPE.S32:
            if storage:
                self.storage = int(storage)

            range_min = (range[0] if range[0] else INT_SIZES.S32_MIN.value)
            range_max = (range[1] if range[1] else INT_SIZES.S32_MAX.value)
            self.range = (int(range_min), int(range_max))
        elif dtype == REG_DTYPE.U32:
            if storage:
                self.storage = int(storage)

            range_min = range[0] if range[0] else 0
            range_max = (range[1] if range[1] else INT_SIZES.U32_MAX.value)
            self.range = (int(range_min), int(range_max))
        if dtype == REG_DTYPE.S64:
            if storage:
                self.storage = int(storage)

            range_min = (range[0] if range[0] else INT_SIZES.S64_MIN.value)
            range_max = (range[1] if range[1] else INT_SIZES.S64_MAX.value)
            self.range = (int(range_min), int(range_max))
        elif dtype == REG_DTYPE.U64:
            if storage:
                self.storage = int(storage)

            range_min = range[0] if range[0] else 0
            range_max = (range[1] if range[1] else INT_SIZES.U64_MAX.value)
            self.range = (int(range_min), int(range_max))
        elif dtype == REG_DTYPE.FLOAT:
            if storage:
                self.storage = float(storage)

            range_min = (range[0] if range[0] else INT_SIZES.S32_MIN.value)
            range_max = (range[1] if range[1] else INT_SIZES.S32_MAX.value)
            self.range = (float(range_min), float(range_max))
        else:
            self.storage_valid = 0

        for enum in enums:
            for key, value in enum.items():
                dictionary = {
                    'label': value,
                    'value': int(key)
                }
                self.enums.append(dictionary)

    @property
    def idx(self):
        """int: Register index."""
        return self.__idx

    @property
    def subidx(self):
        """int: Register subindex."""
        return self.__subidx
