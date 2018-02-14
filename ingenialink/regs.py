import collections
from enum import Enum

from ._ingenialink import ffi, lib
from ._utils import cstr, pstr, raise_null, raise_err


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


class RegisterLabels(collections.MutableMapping):
    """ Register Labels dictionary.

        Args:
            labels (dict, optional): Labels.

        Raises:
            ILCreationError: If the dictionary could not be created.
    """

    def __init__(self, labels=None):
        _labels = lib.il_reg_labels_create()
        raise_null(_labels)

        self._labels = ffi.gc(_labels, lib.il_reg_labels_destroy)

        if labels:
            for lang, content in labels.items():
                lib.il_reg_labels_set(self._labels, cstr(lang), cstr(content))

            self._load_langs()

    @classmethod
    def _from_labels(cls, _labels):
        """ Create a new class instance from an existing labels dictionary. """

        inst = cls.__new__(cls)
        inst._labels = _labels

        inst._load_langs()

        return inst

    def _load_langs(self):
        """ Load languages from dictionary (cache). """

        langs = lib.il_reg_labels_langs_get(self._labels)

        self._langs = []
        i = 0
        lang = langs[0]
        while lang != ffi.NULL:
            self._langs.append(pstr(lang))
            i += 1
            lang = langs[i]

        lib.il_reg_labels_langs_destroy(langs)

    def __getitem__(self, lang):
        content_p = ffi.new('char **')
        r = lib.il_reg_labels_get(self._labels, cstr(lang), content_p)
        raise_err(r)

        return pstr(content_p[0])

    def __setitem__(self, lang, content):
        lib.il_reg_labels_set(self._labels, cstr(lang), cstr(content))
        self._langs.append(lang)

    def __delitem__(self, lang):
        lib.il_reg_labels_del(self._labels, cstr(lang))
        self._langs.remove(lang)

    def __len__(self):
        return len(self._langs)

    def __iter__(self):
        return iter(self._langs)


class Register(object):
    """ Register.

        Args:
            address (int): Address.
            dtype (REG_DTYPE): Data type.
            access (REG_ACCESS): Access type.
            phy (REG_PHY, optional): Physical units.
            labels (dict, optional): Register labels.

        Raises:
            TypeError: If any of the parameters has invalid type.
    """

    def __init__(self, address, dtype, access, phy=REG_PHY.NONE, labels=None):
        if not isinstance(dtype, REG_DTYPE):
            raise TypeError('Invalid data type')

        if not isinstance(access, REG_ACCESS):
            raise TypeError('Invalid access type')

        if not isinstance(phy, REG_PHY):
            raise TypeError('Invalid physical units type')

        self._labels = RegisterLabels(labels)

        self._reg = ffi.new('il_reg_t *',
                            {'address': address,
                             'dtype': dtype.value,
                             'access': access.value,
                             'phy': phy.value,
                             'labels': self._labels._labels})

    def __repr__(self):
        return '<Register: 0x{:08x}, {}, {}, {}>'.format(
                self.address, self.dtype, self.access, self.phy)

    @classmethod
    def _from_register(cls, reg):
        """ Create a new class instance from an existing register. """

        inst = cls.__new__(cls)
        inst._reg = reg
        inst._labels = RegisterLabels._from_labels(reg.labels)

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
    def labels(self):
        """ RegisterLabels: Labels dictionary. """
        return self._labels
