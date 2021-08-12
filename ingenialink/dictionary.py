from abc import ABC, abstractmethod


class Categories(ABC):
    """Categories.

    Args:
        dict_ (il_dict_t *): Ingenia dictionary instance.
    """

    def __init__(self, parent):
        self.__parent = parent
        self.__labels = None
        self.__cat_ids = None

    @abstractmethod
    def labels(self, category_id):
        raise NotImplementedError

    @property
    def category_ids(self):
        raise NotImplementedError


class Dictionary(ABC):
    """Ingenia dictionary Abstract Base Class.

    Args:
        dict_f (str): Dictionary file path.

    Raises:
        ILCreationError: If the dictionary could not be created.
    """
    def __init__(self, dict_f):
        self.__path = dict_f
        self.__registers = []
        self.__version = None
        self.__subnodes = None
        self.__categories = None

    def get_regs(self, subnode):
        raise NotImplementedError

    @property
    def path(self):
        return self.__path

    @path.setter
    def path(self, value):
        self.__path = value

    @property
    def categories(self):
        return self.__categories

    @categories.setter
    def categories(self, value):
        self.__categories = value

    @property
    def version(self):
        return self.__version

    @version.setter
    def version(self, value):
        self.__version = value

    @property
    def subnodes(self):
        return self.__subnodes

    @subnodes.setter
    def subnodes(self, value):
        self.__subnodes = value
