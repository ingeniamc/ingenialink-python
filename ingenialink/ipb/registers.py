from enum import Enum

from .._ingenialink import ffi, lib
from ingenialink.utils._utils import *

import collections

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


def _get_reg_id(reg, subnode=1):
    """Obtain Register and ID.

    Args:
        reg (str, Register): Register.
    """
    if isinstance(reg, str):
        return ffi.NULL, cstr(reg)
    elif isinstance(reg, Register):
        return reg._reg, ffi.NULL

    raise TypeError('Unexpected register type')


class Register(object):
    """Register.

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
        enums (dict, optional): Enumeration values.
        cat_id (str, optional): Category ID.
        scat_id (str, optional): Sub-category ID.
        internal_use (int, optional): Internal use.

    Raises:
        TypeError: If any of the parameters has invalid type.
    """
    def __init__(self, identifier, units, cyclic, address, dtype, access,
                 phy=REG_PHY.NONE, subnode=1, storage=None, range=None,
                 labels={}, enums=[], enums_count=0, cat_id=None, scat_id=None,
                 internal_use=0):
        if not isinstance(dtype, REG_DTYPE):
            raise TypeError('Invalid data type')

        if not isinstance(access, REG_ACCESS):
            raise TypeError('Invalid access type')

        if not isinstance(phy, REG_PHY):
            raise TypeError('Invalid physical units type')

        self._reg = ffi.new('il_reg_t *')

        # initialize register
        self._reg.identifier = ffi.new("char[]", cstr(identifier))
        self._reg.units = ffi.new("char[]", cstr(units))
        self._reg.address = address
        self._reg.subnode = subnode
        self._reg.cyclic = ffi.new("char[]", cstr(cyclic))
        self._reg.dtype = dtype.value
        self._reg.access = access.value
        self._reg.phy = phy.value
        self._reg.internal_use = internal_use

        self._reg.storage_valid = 0 if not storage else 1

        if dtype == REG_DTYPE.S8:
            if storage:
                self._reg.storage.s8 = int(storage)

            self._reg.range.min.s8 = (range[0] if range else
                                      INT_SIZES.S8_MIN.value)
            self._reg.range.max.s8 = (range[1] if range else
                                      INT_SIZES.S8_MAX.value)
        elif dtype == REG_DTYPE.U8:
            if storage:
                self._reg.storage.u8 = int(storage)

            self._reg.range.min.u8 = range[0] if range else 0
            self._reg.range.max.u8 = (range[1] if range else
                                      INT_SIZES.U8_MAX.value)
        if dtype == REG_DTYPE.S16:
            if storage:
                self._reg.storage.s16 = int(storage)

            self._reg.range.min.s16 = (range[0] if range else
                                       INT_SIZES.S16_MIN.value)
            self._reg.range.max.s16 = (range[1] if range else
                                       INT_SIZES.S16_MAX.value)
        elif dtype == REG_DTYPE.U16:
            if storage:
                self._reg.storage.u16 = int(storage)

            self._reg.range.min.u16 = range[0] if range else 0
            self._reg.range.max.u16 = (range[1] if range else
                                       INT_SIZES.U16_MAX.value)
        if dtype == REG_DTYPE.S32:
            if storage:
                self._reg.storage.s32 = int(storage)

            self._reg.range.min.s32 = (range[0] if range else
                                       INT_SIZES.S32_MIN.value)
            self._reg.range.max.s32 = (range[1] if range else
                                       INT_SIZES.S32_MAX.value)
        elif dtype == REG_DTYPE.U32:
            if storage:
                self._reg.storage.u32 = int(storage)

            self._reg.range.min.u32 = range[0] if range else 0
            self._reg.range.max.u32 = (range[1] if range else
                                       INT_SIZES.U32_MAX.value)
        if dtype == REG_DTYPE.S64:
            if storage:
                self._reg.storage.s64 = int(storage)

            self._reg.range.min.s64 = (range[0] if range else
                                       INT_SIZES.S64_MIN.value)
            self._reg.range.max.s64 = (range[1] if range else
                                       INT_SIZES.S64_MAX.value)
        elif dtype == REG_DTYPE.U64:
            if storage:
                self._reg.storage.u64 = int(storage)

            self._reg.range.min.u64 = range[0] if range else 0
            self._reg.range.max.u64 = (range[1] if range else
                                       INT_SIZES.U64_MAX.value)
        elif dtype == REG_DTYPE.FLOAT:
            if storage:
                self._reg.storage.flt = float(storage)

            self._reg.range.min.flt = (range[0] if range else -2147483648)
            self._reg.range.max.flt = (range[1] if range else 2147483647)
        else:
            self._reg.storage_valid = 0

        self._labels = LabelsDictionary(labels)
        self._reg.labels = self._labels._labels
        self._reg.enums_count = enums_count

        self._reg.cat_id = ffi.NULL if not cat_id else cstr(cat_id)

        if not cat_id and scat_id:
            raise ValueError('Sub-category requires a parent category')

        self._reg.scat_id = ffi.NULL if not scat_id else cstr(scat_id)

    def __repr__(self):
        """Obtain register object.

        Returns:
            str: Register information.
        """
        # obtain category/subcategory information
        if self.cat_id:
            cat_info = self.cat_id
            if self.scat_id:
                cat_info += ' + ' + self.scat_id
        else:
            cat_info = 'Uncategorized'

        if self.storage and self.storage_valid:
            storage_info = self.storage
        else:
            storage_info = 'No storage'

        return '<Register: {}, {}, {}, {}, 0x{:08x}, {}{}, {}, {}, [], {},' \
               'ST: {}, [{}], {}>'.format(
                    self.identifier,
                    self.units,
                    self.subnode,
                    self.cyclic,
                    self.address,
                    self.dtype,
                    ' ∊ ' + str(self.range) if self.range else '',
                    self.access,
                    self.phy,
                    self.enums,
                    self.enums_count,
                    storage_info,
                    cat_info,
                    self.internal_use
                )

    @classmethod
    def _from_register(cls, reg):
        """Create a new class instance from an existing register.

        Args:
            reg (Register): Register instance.

        Returns:
            Register: Register object instance copied.
        """
        inst = cls.__new__(cls)
        inst._reg = reg
        inst._labels = LabelsDictionary._from_labels(reg.labels)

        return inst

    @property
    def identifier(self):
        """Obtain register identifier.

        Returns:
            str: Register identifier
        """
        if self._reg.identifier != ffi.NULL:
            return pstr(self._reg.identifier)

        return None

    @property
    def units(self):
        """Obtain register units.

        Returns:
            str: Register units
        """
        if self._reg.units != ffi.NULL:
            return pstr(self._reg.units)

    @property
    def address(self):
        """Obtain register address.

        Returns:
            int: Register address.
        """
        return self._reg.address

    @property
    def subnode(self):
        """Obtain register subnode.

        Returns:
            int: Register subnode.
        """
        return self._reg.subnode

    @property
    def cyclic(self):
        """Obtain register cyclic.

        Returns:
            str: Register cyclic type.
        """
        if self._reg.cyclic != ffi.NULL:
            return pstr(self._reg.cyclic)

    @property
    def dtype(self):
        """Obtain register dtype.

        Returns:
            int: Register data type.
        """
        return REG_DTYPE(self._reg.dtype)

    @property
    def access(self):
        """Obtain register access.

        Returns:
            int: Register access type.
        """
        return REG_ACCESS(self._reg.access)

    @property
    def phy(self):
        """Obtain register physical units.

        Returns:
            int: Register physical units.
        """
        return REG_PHY(self._reg.phy)

    @property
    def storage(self):
        """Obtain register storage.

        Returns:
             int: Register storage.
        """
        if not self._reg.storage_valid:
            return None

        if self.dtype == REG_DTYPE.S8:
            return self._reg.storage.s8
        elif self.dtype == REG_DTYPE.U8:
            return self._reg.storage.u8
        if self.dtype == REG_DTYPE.S16:
            return self._reg.storage.s16
        elif self.dtype == REG_DTYPE.U16:
            return self._reg.storage.u16
        if self.dtype == REG_DTYPE.S32:
            return self._reg.storage.s32
        elif self.dtype == REG_DTYPE.U32:
            return self._reg.storage.u32
        if self.dtype == REG_DTYPE.S64:
            return self._reg.storage.s64
        elif self.dtype == REG_DTYPE.U64:
            return self._reg.storage.u64
        elif self.dtype == REG_DTYPE.FLOAT:
            return self._reg.storage.flt
        else:
            return None

    @property
    def range(self):
        """Obtains register range.

        Returns:
            tuple: Register range (min, max), None if undefined.
        """
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
        elif self.dtype == REG_DTYPE.FLOAT:
            return (self._reg.range.min.flt, self._reg.range.max.flt)

        return None

    @property
    def labels(self):
        """Obtains register labels.

        Returns:
            LabelsDictionary: Labels dictionary.
        """
        return self._labels

    @property
    def enums(self):
        """Obtain enumerations list of the register.

        Returns:
            array: Enumerations of the register.
        """
        if not hasattr(self, '_enums'):
            self._enums = []
            for i in range(0, self._reg.enums_count):
                dict = {
                    'label': pstr(self._reg.enums[i].label),
                    'value': self._reg.enums[i].value
                }
                self._enums.append(dict)
        return self._enums

    @property
    def enums_count(self):
        """Obtain number of enumerations of the register.

        Returns:
            int: Register Enumerations count.
        """
        return self._reg.enums_count

    @property
    def cat_id(self):
        """Category identifier.

        Returns:
            str | None: Current category identifier.
        """
        if self._reg.cat_id != ffi.NULL:
            return pstr(self._reg.cat_id)

        return None

    @property
    def scat_id(self):
        """Subcategory identifier.

        Returns:
            str | None: Current subcategory identifier.
        """
        if self._reg.scat_id != ffi.NULL:
            return pstr(self._reg.scat_id)
        return None

    @property
    def internal_use(self):
        """Internal use check.

        Returns:
            int: Register internal_use.
        """
        return self._reg.internal_use


class LabelsDictionary(collections.MutableMapping):
    """
    Labels dictionary.
    Args:
        labels (dict, optional): Labels.
    Raises:
        ILCreationError: If the dictionary could not be created.
    """
    def __init__(self, labels={}):
        _labels = lib.il_dict_labels_create()
        raise_null(_labels)

        self._labels = ffi.gc(_labels, lib.il_dict_labels_destroy)

        for lang, content in labels.items():
            lib.il_dict_labels_set(self._labels, cstr(lang), cstr(content))

        self._load_langs()

    @classmethod
    def _from_labels(cls, _labels):
        """
        Create a new class instance from an existing labels dictionary.
        """
        inst = cls.__new__(cls)
        inst._labels = _labels

        inst._load_langs()

        return inst

    def _load_langs(self):
        """
        Load languages from dictionary (cache).
        """
        langs = lib.il_dict_labels_langs_get(self._labels)

        self._langs = []
        i = 0
        lang = langs[0]
        while lang != ffi.NULL:
            self._langs.append(pstr(lang))
            i += 1
            lang = langs[i]

        lib.il_dict_labels_langs_destroy(langs)

    def __getitem__(self, lang):
        content_p = ffi.new('char **')
        r = lib.il_dict_labels_get(self._labels, cstr(lang), content_p)
        raise_err(r)

        return pstr(content_p[0])

    def __setitem__(self, lang, content):
        lib.il_dict_labels_set(self._labels, cstr(lang), cstr(content))
        self._langs.append(lang)

    def __delitem__(self, lang):
        lib.il_dict_labels_del(self._labels, cstr(lang))
        self._langs.remove(lang)

    def __len__(self):
        return len(self._langs)

    def __iter__(self):
        return iter(self._langs)