import collections

from ._ingenialink import ffi, lib
from ._utils import cstr, pstr, raise_null, raise_err

from .registers import Register
from .dict_labels import LabelsDictionary


class CategoriesDictionary(collections.Mapping):
    """Categories dictionary.

    Args:
        dict_ (il_dict_t *): Ingenia dictionary instance.
    """

    def __init__(self, dict_):
        self._dict = dict_

        self._load_cat_ids()

    def _load_cat_ids(self):
        """Load category IDs from dictionary."""

        ids = lib.il_dict_cat_ids_get(self._dict)

        self._ids = []
        i = 0
        _id = ids[0]
        while _id != ffi.NULL:
            self._ids.append(pstr(_id))
            i += 1
            _id = ids[i]

        lib.il_dict_cat_ids_destroy(ids)

    def __getitem__(self, _id):
        labels_p = ffi.new('il_dict_labels_t **')
        r = lib.il_dict_cat_get(self._dict, cstr(_id), labels_p)
        raise_err(r)

        return LabelsDictionary._from_labels(labels_p[0])

    def __len__(self):
        return len(self._ids)

    def __iter__(self):
        return iter(self._ids)


class RegistersDictionary(collections.Mapping):
    """Registers dictionary.

    Args:
        dict_ (il_dict_t *): Ingenia dictionary instance.
    """

    def __init__(self, dict_):
        self._dict = dict_

        self._load_reg_ids()

    def _load_reg_ids(self):
        """Load register IDs from dictionary."""

        ids = lib.il_dict_reg_ids_get(self._dict)

        self._ids = []
        i = 0
        _id = ids[0]
        while _id != ffi.NULL:
            self._ids.append(pstr(_id))
            i += 1
            _id = ids[i]

        lib.il_dict_reg_ids_destroy(ids)

    def __getitem__(self, _id):
        reg_p = ffi.new('il_reg_t **')
        r = lib.il_dict_reg_get(self._dict, cstr(_id), reg_p)
        raise_err(r)

        return Register._from_register(reg_p[0])

    def __len__(self):
        return len(self._ids)

    def __iter__(self):
        return iter(self._ids)


class Dictionary(object):
    """Ingenia Dictionary.

    Args:
        dict_f (str): Dictionary file name.

    Raises:
        ILCreationError: If the dictionary could not be created.
    """

    def __init__(self, dict_f):
        dict_ = lib.il_dict_create(cstr(dict_f))
        raise_null(dict_)

        self._dict = ffi.gc(dict_, lib.il_dict_destroy)

        self._rdict = RegistersDictionary(self._dict)
        self._cdict = CategoriesDictionary(self._dict)

    @classmethod
    def _from_dict(cls, dict_):
        """Create a new class instance from an existing dictionary."""

        inst = cls.__new__(cls)
        inst._dict = dict_

        inst._rdict = RegistersDictionary(inst._dict)
        inst._cdict = CategoriesDictionary(inst._dict)

        return inst

    @property
    def regs(self):
        """RegistersDictionary: Registers dictionary."""
        return self._rdict

    @property
    def cats(self):
        """CategoriesDictionary: Categories dictionary."""
        return self._cdict
