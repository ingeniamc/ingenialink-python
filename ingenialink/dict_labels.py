import collections

from ._ingenialink import ffi, lib
from ._utils import cstr, pstr, raise_null, raise_err


class LabelsDictionary(collections.MutableMapping):
    """Labels dictionary.

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
        """Create a new class instance from an existing labels dictionary."""

        inst = cls.__new__(cls)
        inst._labels = _labels

        inst._load_langs()

        return inst

    def _load_langs(self):
        """Load languages from dictionary (cache)."""

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
