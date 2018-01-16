import collections

from ._ingenialink import ffi, lib
from ._utils import cstr, pstr, raise_null, raise_err
from .regs import Register


class Dictionary(collections.Mapping):
    """ Dictionary.

        Args:
            dict_f (str): Dictionary file name.

        Raises:
            ILCreationError: If the dictionary could not be created.
    """

    def __init__(self, dict_f):
        _dict = lib.il_dict_create(cstr(dict_f))
        raise_null(_dict)

        self._dict = ffi.gc(_dict, lib.il_dict_destroy)

        self._load_ids()

    @classmethod
    def _from_dict(cls, _dict):
        """ Create a new class instance from an existing dictionary. """

        inst = cls.__new__(cls)
        inst._dict = _dict

        inst._load_ids()

        return inst

    def _load_ids(self):
        """ Load IDs from dictionary. """

        ids = lib.il_dict_ids_get(self._dict)

        self._ids = []
        i = 0
        _id = ids[0]
        while _id != ffi.NULL:
            self._ids.append(pstr(_id))
            i += 1
            _id = ids[i]

        lib.il_dict_ids_destroy(ids)

    def __getitem__(self, _id):
        reg_p = ffi.new('il_reg_t **')
        r = lib.il_dict_reg_get(self._dict, cstr(_id), reg_p)
        raise_err(r)

        return Register._from_register(reg_p[0])

    def __len__(self):
        return len(self._ids)

    def __iter__(self):
        return iter(self._ids)
