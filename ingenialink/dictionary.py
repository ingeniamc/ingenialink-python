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
        dictionary_path (str): Dictionary file path.

    Raises:
        ILCreationError: If the dictionary could not be created.
    """
    def __init__(self, dictionary_path):
        self.__path = dictionary_path
        self.__version = None
        self.__subnodes = None

        self.__categories = None
        self.__registers = []
        self.__errors = None

    def registers(self, subnode):
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
    def errors(self):
        return self.__errors

    @errors.setter
    def errors(self, value):
        self.__errors = value

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
