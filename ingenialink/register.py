from enum import Enum

from ._ingenialink import ffi, lib
from ingenialink.utils._utils import *

from abc import ABC

# CANOPEN DTYPES
IL_REG_DTYPE_DOMAIN = 15


class REG_DTYPE(Enum):
    """Data Type."""
    U8 = lib.IL_REG_DTYPE_U8
    """Unsigned 8-bit integer."""
    S8 = lib.IL_REG_DTYPE_S8
    """Signed 8-bit integer."""
    U16 = lib.IL_REG_DTYPE_U16
    """Unsigned 16-bit integer."""
    S16 = lib.IL_REG_DTYPE_S16
    """Signed 16-bit integer."""
    U32 = lib.IL_REG_DTYPE_U32
    """Unsigned 32-bit integer."""
    S32 = lib.IL_REG_DTYPE_S32
    """Signed 32-bit integer."""
    U64 = lib.IL_REG_DTYPE_U64
    """Unsigned 64-bit integer."""
    S64 = lib.IL_REG_DTYPE_S64
    """Signed 64-bit integer."""
    FLOAT = lib.IL_REG_DTYPE_FLOAT
    """Float."""
    STR = lib.IL_REG_DTYPE_STR
    """String."""
    DOMAIN = IL_REG_DTYPE_DOMAIN
    """Domain."""


class REG_ACCESS(Enum):
    """Access Type."""
    RW = lib.IL_REG_ACCESS_RW
    """Read/Write."""
    RO = lib.IL_REG_ACCESS_RO
    """Read-only."""
    WO = lib.IL_REG_ACCESS_WO
    """Write-only."""


class REG_PHY(Enum):
    """Physical Units."""
    NONE = lib.IL_REG_PHY_NONE
    """None."""
    TORQUE = lib.IL_REG_PHY_TORQUE
    """Torque."""
    POS = lib.IL_REG_PHY_POS
    """Position."""
    VEL = lib.IL_REG_PHY_VEL
    """Velocity."""
    ACC = lib.IL_REG_PHY_ACC
    """Acceleration."""
    VOLT_REL = lib.IL_REG_PHY_VOLT_REL
    """Relative voltage (DC)."""
    RAD = lib.IL_REG_PHY_RAD
    """Radians."""


def dtype_size(dtype):
    sizes = {
        REG_DTYPE.U8: 1,
        REG_DTYPE.S8: 1,
        REG_DTYPE.U16: 2,
        REG_DTYPE.S16: 2,
        REG_DTYPE.U32: 4,
        REG_DTYPE.S32: 4,
        REG_DTYPE.U64: 8,
        REG_DTYPE.S64: 8,
        REG_DTYPE.FLOAT: 4
    }
    return sizes[dtype]


def _get_reg_id(reg):
    """Obtain Register and ID.

    Args:
        reg (str, Register): Register.
    """
    if isinstance(reg, str):
        return ffi.NULL, cstr(reg)
    elif isinstance(reg, Register):
        return reg._reg, ffi.NULL

    raise TypeError('Unexpected register type')


class Register(ABC):
    """Register.

    Args:
        identifier (str): Identifier.
        units (str): Units.
        cyclic (str): Cyclic typed register.
        dtype (REG_DTYPE): Data type.
        access (REG_ACCESS): Access type.
        phy (REG_PHY, optional): Physical units.
        subnode (int): Subnode
        storage (any, optional): Storage.
        range (tuple, optional): Range (min, max).
        labels (dict, optional): Register labels.
        enums (dict, optional): Enumeration values.
        cat_id (str, optional): Category ID.
        scat_id (str, optional): Sub-category ID.
        internal_use (int, optional): Internal use.

    Raises:
        TypeError: If any of the parameters has invalid type.

    """
    def __init__(self, identifier, units, cyclic, dtype, access,
                 phy=REG_PHY.NONE, subnode=1, storage=None, range=None,
                 labels={}, enums=[], enums_count=0, cat_id=None, scat_id=None,
                 internal_use=0):
        if not isinstance(dtype, REG_DTYPE):
            raise TypeError('Invalid data type')

        if not isinstance(access, REG_ACCESS):
            raise TypeError('Invalid access type')

        if not isinstance(phy, REG_PHY):
            raise TypeError('Invalid physical units type')

        self.__identifier = identifier
        self.__units = units
        self.__subnode = subnode
        self.__cyclic = cyclic
        self.__dtype = dtype.value
        self.__access = access.value
        self.__phy = phy.value
        self.__storage = storage
        self.__storage_valid = 0 if not storage else 1
        self.__internal_use = internal_use
        self.__range = (None, None) if not range else range
        self.__labels = labels
        self.__enums = enums
        self.__enums_count = enums_count
        self.__cat_id = cat_id
        self.__scat_id = scat_id

    @property
    def identifier(self):
        """str: Register identifier."""
        return self.__identifier

    @identifier.setter
    def identifier(self, value):
        self.__identifier = value

    @property
    def units(self):
        """str: Units of the register."""
        return self.__units

    @units.setter
    def units(self, value):
        self.__units = value

    @property
    def subnode(self):
        """int: Target subnode of the register."""
        return self.__subnode

    @subnode.setter
    def subnode(self, value):
        self.__subnode = value

    @property
    def cyclic(self):
        """str: Defines if the register is cyclic."""
        return self.__cyclic

    @cyclic.setter
    def cyclic(self, value):
        self.__cyclic = value

    @property
    def dtype(self):
        """REG_DTYPE: Data type of the register."""
        return REG_DTYPE(self.__dtype)

    @dtype.setter
    def dtype(self, value):
        self.__dtype = value

    @property
    def access(self):
        """REG_ACCESS: Access type of the register."""
        return REG_ACCESS(self.__access)

    @access.setter
    def access(self, value):
        self.__access = value

    @property
    def phy(self):
        """REG_PHY: Physical units of the register."""
        return REG_PHY(self.__phy)

    @phy.setter
    def phy(self, value):
        self.__phy = value

    @property
    def storage(self):
        """any: Defines if the register needs to be stored."""
        if not self.__storage_valid:
            return None

        if self.dtype in [REG_DTYPE.S8, REG_DTYPE.U8, REG_DTYPE.S16,
                          REG_DTYPE.U16, REG_DTYPE.S32, REG_DTYPE.U32,
                          REG_DTYPE.S64, REG_DTYPE.U64, REG_DTYPE.FLOAT]:
            return self.__storage
        else:
            return None

    @storage.setter
    def storage(self, value):
        self.__storage = value

    @property
    def storage_valid(self):
        """bool: Defines if the register storage is valid."""
        return self.__storage_valid

    @storage_valid.setter
    def storage_valid(self, value):
        self.__storage_valid = value

    @property
    def range(self):
        """tuple: Containing the minimum and the maximum values of the register."""
        if self.__range:
            return self.__range[0], self.__range[1]
        return None

    @range.setter
    def range(self, value):
        self.__range = value

    @property
    def labels(self):
        """dict: Containing the labels of the register."""
        return self.__labels

    @labels.setter
    def labels(self, value):
        self.__labels = value

    @property
    def enums(self):
        """dict: Containing all the enums for the register."""
        return self.__enums

    @enums.setter
    def enums(self, value):
        self.__enums = value

    @property
    def enums_count(self):
        """int: The number of the enums in the register."""
        return self.__enums_count

    @enums_count.setter
    def enums_count(self, value):
        self.__enums_count = value

    @property
    def cat_id(self):
        """str: Category ID"""
        return self.__cat_id

    @cat_id.setter
    def cat_id(self, value):
        self.__cat_id = value

    @property
    def scat_id(self):
        """str: Sub-Category ID"""
        return self.__scat_id

    @scat_id.setter
    def scat_id(self, value):
        self.__scat_id = value

    @property
    def internal_use(self):
        """int: Defines if the register is only for internal uses."""
        return self.__internal_use

    @internal_use.setter
    def internal_use(self, value):
        self.__internal_use = value
