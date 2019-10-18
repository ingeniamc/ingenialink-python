from enum import Enum

from .._ingenialink import lib

from .._utils import INT_SIZES
# from .dict_labels import LabelsDictionary

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
HOLA_VALUE = 3

class Register(object):
    """ Register.

        Args:
            identifier (str): Identifier.
            units (str): Units.
            address (int): Address.
            dtype (REG_DTYPE): Data type.
            access (REG_ACCESS): Access type.
            phy (REG_PHY, optional): Physical units.
            subnode (int): Subnode
            storage (any, optional): Storage.
            range (tuple, optional): Range (min, max).
            labels (dict, optional): Register labels.
            cat_id (str, optional): Category ID.
            scat_id (str, optional): Sub-category ID.
            internal_use (int, optional): Internal use.

        Raises:
            TypeError: If any of the parameters has invalid type.
    """

    def __init__(self, identifier, units, cyclic, idx, subidx, dtype, access, phy=REG_PHY.NONE, subnode=1, storage=None,
                 range=None, labels={}, enums=[], enums_count=0, cat_id=None, scat_id=None, internal_use=0):
        if not isinstance(dtype, REG_DTYPE):
            raise TypeError('Invalid data type')

        if not isinstance(access, REG_ACCESS):
            raise TypeError('Invalid access type')

        if not isinstance(phy, REG_PHY):
            raise TypeError('Invalid physical units type')

        # initialize register
        self.__identifier = identifier
        self.__units = units
        self.__idx = idx
        self.__subidx = subidx
        self.__subnode = subnode
        self.__cyclic = cyclic
        self.__dtype = dtype.value
        self.__access = access.value
        self.__phy = phy.value
        self.__internal_use = internal_use
        self.__storage = storage

        self__storage_valid = 0 if not storage else 1

        # if dtype == REG_DTYPE.S8:
        #     if storage:
        #         self.__storage.s8 = int(storage)
        #
        #     self.__range.min.s8 = (range[0] if range else
        #                               INT_SIZES.S8_MIN.value)
        #     self._reg.range.max.s8 = (range[1] if range else
        #                               INT_SIZES.S8_MAX.value)
        # elif dtype == REG_DTYPE.U8:
        #     if storage:
        #         self._reg.storage.u8 = int(storage)
        #
        #     self._reg.range.min.u8 = range[0] if range else 0
        #     self._reg.range.max.u8 = (range[1] if range else
        #                               INT_SIZES.U8_MAX.value)
        # if dtype == REG_DTYPE.S16:
        #     if storage:
        #         self._reg.storage.s16 = int(storage)
        #
        #     self._reg.range.min.s16 = (range[0] if range else
        #                                INT_SIZES.S16_MIN.value)
        #     self._reg.range.max.s16 = (range[1] if range else
        #                                INT_SIZES.S16_MAX.value)
        # elif dtype == REG_DTYPE.U16:
        #     if storage:
        #         self._reg.storage.u16 = int(storage)
        #
        #     self._reg.range.min.u16 = range[0] if range else 0
        #     self._reg.range.max.u16 = (range[1] if range else
        #                                INT_SIZES.U16_MAX.value)
        # if dtype == REG_DTYPE.S32:
        #     if storage:
        #         self._reg.storage.s32 = int(storage)
        #
        #     self._reg.range.min.s32 = (range[0] if range else
        #                                INT_SIZES.S32_MIN.value)
        #     self._reg.range.max.s32 = (range[1] if range else
        #                                INT_SIZES.S32_MAX.value)
        # elif dtype == REG_DTYPE.U32:
        #     if storage:
        #         self._reg.storage.u32 = int(storage)
        #
        #     self._reg.range.min.u32 = range[0] if range else 0
        #     self._reg.range.max.u32 = (range[1] if range else
        #                                INT_SIZES.U32_MAX.value)
        # if dtype == REG_DTYPE.S64:
        #     if storage:
        #         self._reg.storage.s64 = int(storage)
        #
        #     self._reg.range.min.s64 = (range[0] if range else
        #                                INT_SIZES.S64_MIN.value)
        #     self._reg.range.max.s64 = (range[1] if range else
        #                                INT_SIZES.S64_MAX.value)
        # elif dtype == REG_DTYPE.U64:
        #     if storage:
        #         self._reg.storage.u64 = int(storage)
        #
        #     self._reg.range.min.u64 = range[0] if range else 0
        #     self._reg.range.max.u64 = (range[1] if range else
        #                                INT_SIZES.U64_MAX.value)
        # elif dtype == REG_DTYPE.FLOAT:
        #     if storage:
        #         self._reg.storage.flt = float(storage)
        # else:
        #     self._reg.storage_valid = 0

        # self._labels = LabelsDictionary(labels)
        # self._reg.labels = self._labels._labels
        # self._reg.enums_count = enums_count
        #
        # self._reg.cat_id = ffi.NULL if not cat_id else cstr(cat_id)
        #
        # if not cat_id and scat_id:
        #     raise ValueError('Sub-category requires a parent category')
        #
        # self._reg.scat_id = ffi.NULL if not scat_id else cstr(scat_id)

    @property
    def identifier(self):
        """ str: Register identifier """
        return self.__identifier

    @property
    def units(self):
        """ str: Register units """
        return self.__units


    @property
    def idx(self):
        """ int: Register index. """
        return self.__idx

    @property
    def subidx(self):
        """ int: Register subindex. """
        return self.__subidx

    @property
    def subnode(self):
        """ int: Register subnode. """
        return self.__subnode

    @property
    def cyclic(self):
        """ str: Register cyclic type. """
        return self.__cyclic

    @property
    def dtype(self):
        """ int: Register data type. """
        return REG_DTYPE(self.__dtype)

    @property
    def access(self):
        """ int: Register access type. """
        return REG_ACCESS(self.__access)

    @property
    def phy(self):
        """ int: Register physical units. """
        return REG_PHY(self.__phy)

    @property
    def storage(self):
        """ Register storage. """
        if not self.__storage_valid:
            return None

        if self.dtype == REG_DTYPE.S8:
            return self.__storage.s8
        elif self.dtype == REG_DTYPE.U8:
            return self.__storage.u8
        if self.dtype == REG_DTYPE.S16:
            return self.__storage.s16
        elif self.dtype == REG_DTYPE.U16:
            return self.__storage.u16
        if self.dtype == REG_DTYPE.S32:
            return self.__storage.s32
        elif self.dtype == REG_DTYPE.U32:
            return self.__storage.u32
        if self.dtype == REG_DTYPE.S64:
            return self.__storage.s64
        elif self.dtype == REG_DTYPE.U64:
            return self.__storage.u64
        elif self.dtype == REG_DTYPE.FLOAT:
            return self.__storage.flt
        else:
            return None

    # @property
    # def range(self):
    #     """ tuple: Register range (min, max), None if undefined. """
    #
    #     if self.dtype == REG_DTYPE.S8:
    #         return (self.__range.min.s8, self.__range.max.s8)
    #     elif self.dtype == REG_DTYPE.U8:
    #         return (self.__range.min.u8, self.__range.max.u8)
    #     if self.dtype == REG_DTYPE.S16:
    #         return (self.__range.min.s16, self.__range.max.s16)
    #     elif self.dtype == REG_DTYPE.U16:
    #         return (self.__range.min.u16, self.__range.max.u16)
    #     if self.dtype == REG_DTYPE.S32:
    #         return (self._reg.range.min.s32, self.__range.max.s32)
    #     elif self.dtype == REG_DTYPE.U32:
    #         return (self.__range.min.u32, self.__range.max.u32)
    #     if self.dtype == REG_DTYPE.S64:
    #         return (self.__range.min.s64, self.__range.max.s64)
    #     elif self.dtype == REG_DTYPE.U64:
    #         return (self.__range.min.u64, self.__range.max.u64)
    #
    #     return None

    # @property
    # def labels(self):
    #     """ LabelsDictionary: Labels dictionary. """
    #     return self._labels
    #
    # @property
    # def enums(self):
    #     """ Enumerations list. """
    #     if not hasattr(self, '_enums'):
    #         self._enums = []
    #         for i in range(0, self._reg.enums_count):
    #             dict = {
    #                 'label': pstr(self._reg.enums[i].label),
    #                 'value': self._reg.enums[i].value
    #             }
    #             self._enums.append(dict)
    #     return self._enums
    #
    # @property
    # def enums_count(self):
    #     """ int: Register Enumerations count. """
    #     return self._reg.enums_count
    #
    # @property
    # def cat_id(self):
    #     """Category ID."""
    #     if self._reg.cat_id != ffi.NULL:
    #         return pstr(self._reg.cat_id)
    #
    #     return None
    #
    # @property
    # def scat_id(self):
    #     """Sub-category ID."""
    #     if self._reg.scat_id != ffi.NULL:
    #         return pstr(self._reg.scat_id)
    #     return None

    @property
    def internal_use(self):
        """ int: Register internal_use. """
        return self.__internal_use
