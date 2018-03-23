from enum import Enum

from ._ingenialink import ffi, lib
from ._utils import cstr, pstr, INT_SIZES

from .dict_labels import LabelsDictionary


class REG_DTYPE(Enum):
    """ Data Type. """

    U8 = lib.IL_REG_DTYPE_U8
    """ Unsigned 8-bit integer. """
    S8 = lib.IL_REG_DTYPE_S8
    """ Signed 8-bit integer. """
    U16 = lib.IL_REG_DTYPE_U16
    """ Unsigned 16-bit integer. """
    S16 = lib.IL_REG_DTYPE_S16
    """ Signed 16-bit integer. """
    U32 = lib.IL_REG_DTYPE_U32
    """ Unsigned 32-bit integer. """
    S32 = lib.IL_REG_DTYPE_S32
    """ Signed 32-bit integer. """
    U64 = lib.IL_REG_DTYPE_U64
    """ Unsigned 64-bit integer. """
    S64 = lib.IL_REG_DTYPE_S64
    """ Signed 64-bit integer. """
    FLOAT = lib.IL_REG_DTYPE_FLOAT
    """ Float. """
    STR = lib.IL_REG_DTYPE_STR
    """ String. """


class REG_ACCESS(Enum):
    """ Access Type. """

    RW = lib.IL_REG_ACCESS_RW
    """ Read/Write. """
    RO = lib.IL_REG_ACCESS_RO
    """ Read-only. """
    WO = lib.IL_REG_ACCESS_WO
    """ Write-only. """


class REG_PHY(Enum):
    """ Physical Units. """

    NONE = lib.IL_REG_PHY_NONE
    """ None. """
    TORQUE = lib.IL_REG_PHY_TORQUE
    """ Torque. """
    POS = lib.IL_REG_PHY_POS
    """ Position. """
    VEL = lib.IL_REG_PHY_VEL
    """ Velocity. """
    ACC = lib.IL_REG_PHY_ACC
    """ Acceleration. """
    VOLT_REL = lib.IL_REG_PHY_VOLT_REL
    """ Relative voltage (DC). """
    RAD = lib.IL_REG_PHY_RAD
    """ Radians. """


def _get_reg_id(reg):
    """ Obtain Register and ID.

        Args:
            reg (str, Register): Register.
    """

    if isinstance(reg, str):
        return ffi.NULL, cstr(reg)
    elif isinstance(reg, Register):
        return reg._reg, ffi.NULL

    raise TypeError('Unexpected register type')


class Register(object):
    """ Register.

        Args:
            address (int): Address.
            dtype (REG_DTYPE): Data type.
            access (REG_ACCESS): Access type.
            phy (REG_PHY, optional): Physical units.
            range (tuple, optional): Range (min, max).
            labels (dict, optional): Register labels.
            cat_id (str, optional): Category ID.

        Raises:
            TypeError: If any of the parameters has invalid type.
    """

    def __init__(self, address, dtype, access, phy=REG_PHY.NONE, range=None,
                 labels={}, cat_id=None):
        if not isinstance(dtype, REG_DTYPE):
            raise TypeError('Invalid data type')

        if not isinstance(access, REG_ACCESS):
            raise TypeError('Invalid access type')

        if not isinstance(phy, REG_PHY):
            raise TypeError('Invalid physical units type')

        self._reg = ffi.new('il_reg_t *')

        # initialize register
        self._reg.address = address
        self._reg.dtype = dtype.value
        self._reg.access = access.value
        self._reg.phy = phy.value

        if dtype == REG_DTYPE.S8:
            self._reg.range.min.s8 = (range[0] if range else
                                      INT_SIZES.S8_MIN.value)
            self._reg.range.max.s8 = (range[1] if range else
                                      INT_SIZES.S8_MAX.value)
        elif dtype == REG_DTYPE.U8:
            self._reg.range.min.u8 = range[0] if range else 0
            self._reg.range.max.u8 = (range[1] if range else
                                      INT_SIZES.U8_MAX.value)
        if dtype == REG_DTYPE.S16:
            self._reg.range.min.s16 = (range[0] if range else
                                       INT_SIZES.S16_MIN.value)
            self._reg.range.max.s16 = (range[1] if range else
                                       INT_SIZES.S16_MAX.value)
        elif dtype == REG_DTYPE.U16:
            self._reg.range.min.u16 = range[0] if range else 0
            self._reg.range.max.u16 = (range[1] if range else
                                       INT_SIZES.U16_MAX)
        if dtype == REG_DTYPE.S32:
            self._reg.range.min.s32 = (range[0] if range else
                                       INT_SIZES.S32_MIN.value)
            self._reg.range.max.s32 = (range[1] if range else
                                       INT_SIZES.S32_MAX.value)
        elif dtype == REG_DTYPE.U32:
            self._reg.range.min.u32 = range[0] if range else 0
            self._reg.range.max.u32 = (range[1] if range else
                                       INT_SIZES.U32_MAX.value)
        if dtype == REG_DTYPE.S64:
            self._reg.range.min.s64 = (range[0] if range else
                                       INT_SIZES.S64_MIN.value)
            self._reg.range.max.s64 = (range[1] if range else
                                       INT_SIZES.S64_MAX.value)
        elif dtype == REG_DTYPE.U64:
            self._reg.range.min.u64 = range[0] if range else 0
            self._reg.range.max.u64 = (range[1] if range else
                                       INT_SIZES.U64_MAX.value)

        self._labels = LabelsDictionary(labels)
        self._reg.labels = self._labels._labels

        self._reg.cat_id = ffi.NULL if not cat_id else cstr(cat_id)

    def __repr__(self):
        return '<Register: 0x{:08x}, {}{}, {}, {}>'.format(
                self.address, self.dtype,
                ' ∊ ' + str(self.range) if self.range else '', self.access,
                self.phy)

    @classmethod
    def _from_register(cls, reg):
        """ Create a new class instance from an existing register. """

        inst = cls.__new__(cls)
        inst._reg = reg
        inst._labels = LabelsDictionary._from_labels(reg.labels)

        return inst

    @property
    def address(self):
        """ int: Register address. """
        return self._reg.address

    @property
    def dtype(self):
        """ int: Register data type. """
        return REG_DTYPE(self._reg.dtype)

    @property
    def access(self):
        """ int: Register access type. """
        return REG_ACCESS(self._reg.access)

    @property
    def phy(self):
        """ int: Register physical units. """
        return REG_PHY(self._reg.phy)

    @property
    def range(self):
        """ tuple: Register range (min, max), None if undefined. """

        if self.dtype == REG_DTYPE.S8:
            return (self._reg.range.min.s8, self._reg.range.max.s8)
        elif self.dtype == REG_DTYPE.U8:
            return (self._reg.range.min.u8, self._reg.range.max.u8)
        if self.dtype == REG_DTYPE.S16:
            return (self._reg.range.min.s16, self._reg.range.max.s16)
        elif self.dtype == REG_DTYPE.U16:
            return (self._reg.range.min.u16, self._reg.range.max.u16)
        if self.dtype == REG_DTYPE.S32:
            return (self._reg.range.min.s32, self._reg.range.max.s32)
        elif self.dtype == REG_DTYPE.U32:
            return (self._reg.range.min.u32, self._reg.range.max.u32)
        if self.dtype == REG_DTYPE.S64:
            return (self._reg.range.min.s64, self._reg.range.max.s64)
        elif self.dtype == REG_DTYPE.U64:
            return (self._reg.range.min.u64, self._reg.range.max.u64)

        return None

    @property
    def labels(self):
        """ LabelsDictionary: Labels dictionary. """
        return self._labels

    @property
    def cat_id(self):
        """Category ID."""
        if self._reg.cat_id != ffi.NULL:
            return pstr(self._reg.cat_id)

        return None
