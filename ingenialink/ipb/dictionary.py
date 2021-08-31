import collections

from .._ingenialink import ffi, lib
from ingenialink.utils._utils import cstr, pstr, raise_null, raise_err

from ingenialink.ipb.register import LabelsDictionary, ipb_register_from_cffi
from ..dictionary import Dictionary, Categories


class SubCategories:
    """Sub-categories.

    Args:
        dict_ (CData): Ingenia dictionary instance.
        cat_id (str): Category ID.

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

    def labels(self, scat_id):
        """Obtain labels for a certain sub-category identifiers.

        Returns:
            dict: Labels dictionary.

        """
        labels_p = ffi.new('il_dict_labels_t **')
        r = lib.il_dict_scat_get(self._dict, cstr(self._cat_id), cstr(scat_id),
                                 labels_p)
        raise_err(r)

        return LabelsDictionary._from_labels(labels_p[0])

    @property
    def subcategory_ids(self):
        """Obtain all sub-category identifiers.

        Returns:
            list: Sub-category identifiers.

        """
        return self._scat_ids


class IPBCategories(Categories):
    """IPB Categories for the dictionary.

    Args:
        ipb_dictionary (IPBDictionary): Ingenia dictionary instance.

    """

    def __init__(self, ipb_dictionary):
        super(IPBCategories, self).__init__(ipb_dictionary)
        self.__ipb_dictionary = ipb_dictionary
        self._load_cat_ids()

    def _load_cat_ids(self):
        """Load category IDs from dictionary."""
        cat_ids = lib.il_dict_cat_ids_get(self.__ipb_dictionary._cffi_dictionary)

        self._cat_ids = []
        i = 0
        cat_id = cat_ids[0]
        while cat_id != ffi.NULL:
            self._cat_ids.append(pstr(cat_id))
            i += 1
            cat_id = cat_ids[i]

        lib.il_dict_cat_ids_destroy(cat_ids)

    def labels(self, category_id):
        """Obtain labels for a certain category ID.

        Returns:
            dict: Labels dictionary.

        """
        labels_p = ffi.new('il_dict_labels_t **')
        r = lib.il_dict_cat_get(self.__ipb_dictionary._cffi_dictionary,
                                cstr(category_id), labels_p)
        raise_err(r)

        return LabelsDictionary._from_labels(labels_p[0])

    def subcategories(self, cat_id):
        """Obtain all sub-categories.

        Returns:
            SubCategories: Sub-categories.

        """
        return SubCategories(self.__ipb_dictionary._cffi_dictionary, cat_id)

    @property
    def category_ids(self):
        """Obtain all Category Identifiers.

        Returns:
            list: Category IDs.

        """
        return self._cat_ids


class RegistersDictionary(collections.Mapping):
    """Registers dictionary.

    Args:
        dict_ (CData): Ingenia dictionary instance.

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

        return ipb_register_from_cffi(reg_p[0])

    def __len__(self):
        return len(self._ids)

    def __iter__(self):
        return iter(self._ids)


class IPBDictionary(Dictionary):
    """IPB Ingenia Dictionary.

    Args:
        dictionary (str): Dictionary file name.

    Raises:
        ILCreationError: If the dictionary could not be created.

    """
    def __init__(self, dictionary):
        super(IPBDictionary, self).__init__(dictionary)
        dict_ = lib.il_dict_create(cstr(dictionary))
        raise_null(dict_)

        self._cffi_dictionary = ffi.gc(dict_, lib.il_dict_destroy)

        self.version = pstr(lib.il_dict_version_get(dict_))
        self.subnodes = lib.il_dict_subnodes_get(dict_)

        self.__regs = []
        for subnode in range(0, self.subnodes):
            register = RegistersDictionary(self._cffi_dictionary, subnode)
            self.__regs.append(register)
        self._cats = IPBCategories(self)

    @classmethod
    def _from_dict(cls, dict_):
        """Create a new class instance from an existing dictionary."""
        inst = cls.__new__(cls)
        inst._cffi_dictionary = dict_

        inst.version = pstr(lib.il_dict_version_get(inst._cffi_dictionary))
        inst.subnodes = lib.il_dict_subnodes_get(inst._cffi_dictionary)

        inst.__regs = []
        for subnode in range(0, inst.subnodes):
            rdict = RegistersDictionary(inst._cffi_dictionary, subnode)
            inst.__regs.append(rdict)
        inst._cats = IPBCategories(inst)

        return inst

    def save(self, filename):
        """Save dictionary.

        Args:
            filename (str): Output file name/path.

        """
        r = lib.il_dict_save(self._cffi_dictionary, cstr(filename))
        raise_err(r)

    def registers(self, subnode):
        """Obtain all the registers of a subnode.

        Args:
            subnode (int): Subnode.

        Returns:
            array: List of registers.

        """
        if subnode < self.subnodes:
            return self.__regs[subnode]

    @property
    def errors(self):
        raise NotImplementedError
