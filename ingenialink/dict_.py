import collections

from ._ingenialink import ffi, lib
from ._utils import cstr, pstr, raise_null, raise_err

from .registers import Register, REG_DTYPE
from .dict_labels import LabelsDictionary


class SubCategories(object):
    """Sub-categories.

    Args:
        dict_ (il_dict_t *): Ingenia dictionary instance.
        cat_id (str): Category ID (parent).
    """

    def __init__(self, dict_, cat_id):
        self._dict = dict_
        self._cat_id = cat_id

        self._load_scat_ids()

    def _load_scat_ids(self):
        """Load sub-category IDs from dictionary."""

        scat_ids = lib.il_dict_scat_ids_get(self._dict, cstr(self._cat_id))

        self._scat_ids = []
        i = 0
        scat_id = scat_ids[0]
        while scat_id != ffi.NULL:
            self._scat_ids.append(pstr(scat_id))
            i += 1
            scat_id = scat_ids[i]

        lib.il_dict_scat_ids_destroy(scat_ids)

    @property
    def scat_ids(self):
        """list: Sub-category IDs."""
        return self._scat_ids

    def labels(self, scat_id):
        """Obtain labels for a certain sub-category ID."""

        labels_p = ffi.new('il_dict_labels_t **')
        r = lib.il_dict_scat_get(self._dict, cstr(self._cat_id), cstr(scat_id),
                                 labels_p)
        raise_err(r)

        return LabelsDictionary._from_labels(labels_p[0])


class Categories(object):
    """Categories.

    Args:
        dict_ (il_dict_t *): Ingenia dictionary instance.
    """

    def __init__(self, dict_):
        self._dict = dict_

        self._load_cat_ids()

    def _load_cat_ids(self):
        """Load category IDs from dictionary."""

        cat_ids = lib.il_dict_cat_ids_get(self._dict)

        self._cat_ids = []
        i = 0
        cat_id = cat_ids[0]
        while cat_id != ffi.NULL:
            self._cat_ids.append(pstr(cat_id))
            i += 1
            cat_id = cat_ids[i]

        lib.il_dict_cat_ids_destroy(cat_ids)

    @property
    def cat_ids(self):
        """list: Category IDs."""
        return self._cat_ids

    def labels(self, cat_id):
        """Obtain labels for a certain category ID."""

        labels_p = ffi.new('il_dict_labels_t **')
        r = lib.il_dict_cat_get(self._dict, cstr(cat_id), labels_p)
        raise_err(r)

        return LabelsDictionary._from_labels(labels_p[0])

    def scats(self, cat_id):
        """SubCategories: Sub-categories."""

        return SubCategories(self._dict, cat_id)


class RegistersDictionary(collections.Mapping):
    """Registers dictionary.

    Args:
        dict_ (il_dict_t *): Ingenia dictionary instance.
    """

    def __init__(self, dict_, subnode):
        self._dict = dict_
        self._subnode = subnode

        self._load_reg_ids()

    def _load_reg_ids(self):
        """Load register IDs from dictionary."""
        self._ids = []
        ids = lib.il_dict_reg_ids_get(self._dict, self._subnode)

        i = 0
        _id = ids[0]
        while _id != ffi.NULL:
            self._ids.append(pstr(_id))
            i += 1
            _id = ids[i]

        lib.il_dict_reg_ids_destroy(ids)

    def __getitem__(self, _id):
        reg_p = ffi.new('il_reg_t **')
        r = lib.il_dict_reg_get(self._dict, cstr(_id), reg_p, self._subnode)
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

        # self._rdict = RegistersDictionary(self._dict)
        self._rdict_0 = RegistersDictionary(self._dict, 0)
        self._rdict_1 = RegistersDictionary(self._dict, 1)
        self._rdict_2 = RegistersDictionary(self._dict, 2)
        self._cats = Categories(self._dict)

    @classmethod
    def _from_dict(cls, dict_):
        """Create a new class instance from an existing dictionary."""

        inst = cls.__new__(cls)
        inst._dict = dict_

        # inst._rdict = RegistersDictionary(inst._dict)
        inst._rdict_0 = RegistersDictionary(inst._dict, 0)
        inst._rdict_1 = RegistersDictionary(inst._dict, 1)
        inst._rdict_2 = RegistersDictionary(inst._dict, 2)
        inst._cats = Categories(inst._dict)

        return inst

    def save(self, fname):
        """Save dictionary.

        Args:
            fname (str): Output file name/path.
        """

        r = lib.il_dict_save(self._dict, cstr(fname))
        raise_err(r)

    def get_regs(self, subnode):
        if subnode == 0:
            return self._rdict_0
        elif subnode == 1:
            return self._rdict_1
        else:
            return self._rdict_2

    # @property
    # def regs(self):
    #     """RegistersDictionary: Registers dictionary."""
    #     return self._rdict

    def reg_storage_update(self, id_, value):
        """Update register storage.

        Args:
            id_ (str): Register ID.
            value: Value.
        """

        reg = self.regs[id_]
        value_ = ffi.new('il_reg_value_t')

        if reg.dtype == REG_DTYPE.S8:
            value_.storage.s8 = int(value)
        elif reg.dtype == REG_DTYPE.U8:
            value_.storage.u8 = int(value)
        if reg.dtype == REG_DTYPE.S16:
            value_.storage.s16 = int(value)
        elif reg.dtype == REG_DTYPE.U16:
            value_.storage.u16 = int(value)
        if reg.dtype == REG_DTYPE.S32:
            value_.storage.s32 = int(value)
        elif reg.dtype == REG_DTYPE.U32:
            value_.storage.u32 = int(value)
        if reg.dtype == REG_DTYPE.S64:
            value_.storage.s64 = int(value)
        elif reg.dtype == REG_DTYPE.U64:
            value_.storage.u64 = int(value)
        elif reg.dtype == REG_DTYPE.FLOAT:
            value_.storage.flt = float(value)
        else:
            raise ValueError('Unsupported register data type')

        r = lib.il_dict_reg_storage_update(cstr(id_), value_)
        raise_err(r)

    @property
    def cats(self):
        """Categories: Categories."""
        return self._cats
