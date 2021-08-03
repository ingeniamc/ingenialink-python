from enum import Enum

from .._ingenialink import lib

from ingenialink.utils._utils import *
from ..registers import REG_DTYPE, REG_ACCESS, REG_PHY


class CanopenRegister(object):
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
        ILValueError: If the register is invalid.
        ILAccessError: Register with wrong access type.

    """

    def __init__(self, identifier, units, cyclic, idx, subidx, dtype,
                 access, phy=REG_PHY.NONE, subnode=1, storage=None,
                 range=(None, None), labels={}, enums=[], enums_count=0,
                 cat_id=None, scat_id=None, internal_use=0):
        if not isinstance(dtype, REG_DTYPE):
            raise_err(lib.IL_EINVAL, 'Invalid data type')

        if not isinstance(access, REG_ACCESS):
            raise_err(lib.IL_EACCESS, 'Invalid access type')

        if not isinstance(phy, REG_PHY):
            raise_err(lib.IL_EINVAL, 'Invalid physical units type')

        # Initialize register
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
        self.__storage_valid = 0 if not storage else 1
        self.__range = (None, None) if not range else range

        if dtype == REG_DTYPE.S8:
            if storage:
                self.__storage = int(storage)

            range_min = (range[0] if range[0] else INT_SIZES.S8_MIN.value)
            range_max = (range[1] if range[1] else INT_SIZES.S8_MAX.value)
            self.__range = (int(range_min), int(range_max))
        elif dtype == REG_DTYPE.U8:
            if storage:
                self.__storage = int(storage)

            range_min = range[0] if range[0] else 0
            range_max = (range[1] if range[1] else INT_SIZES.U8_MAX.value)
            self.__range = (int(range_min), int(range_max))
        if dtype == REG_DTYPE.S16:
            if storage:
                self.__storage = int(storage)

            range_min = (range[0] if range[0] else INT_SIZES.S16_MIN.value)
            range_max = (range[1] if range[1] else INT_SIZES.S16_MAX.value)
            self.__range = (int(range_min), int(range_max))
        elif dtype == REG_DTYPE.U16:
            if storage:
                self.__storage = int(storage)

            range_min = range[0] if range[0] else 0
            range_max = (range[1] if range[1] else INT_SIZES.U16_MAX.value)
            self.__range = (int(range_min), int(range_max))
        if dtype == REG_DTYPE.S32:
            if storage:
                self.__storage = int(storage)

            range_min = (range[0] if range[0] else INT_SIZES.S32_MIN.value)
            range_max = (range[1] if range[1] else INT_SIZES.S32_MAX.value)
            self.__range = (int(range_min), int(range_max))
        elif dtype == REG_DTYPE.U32:
            if storage:
                self.__storage = int(storage)

            range_min = range[0] if range[0] else 0
            range_max = (range[1] if range[1] else INT_SIZES.U32_MAX.value)
            self.__range = (int(range_min), int(range_max))
        if dtype == REG_DTYPE.S64:
            if storage:
                self.__storage = int(storage)

            range_min = (range[0] if range[0] else INT_SIZES.S64_MIN.value)
            range_max = (range[1] if range[1] else INT_SIZES.S64_MAX.value)
            self.__range = (int(range_min), int(range_max))
        elif dtype == REG_DTYPE.U64:
            if storage:
                self.__storage = int(storage)

            range_min = range[0] if range[0] else 0
            range_max = (range[1] if range[1] else INT_SIZES.U64_MAX.value)
            self.__range = (int(range_min), int(range_max))
        elif dtype == REG_DTYPE.FLOAT:
            if storage:
                self.__storage = float(storage)

            range_min = (range[0] if range[0] else INT_SIZES.S32_MIN.value)
            range_max = (range[1] if range[1] else INT_SIZES.S32_MAX.value)
            self.__range = (float(range_min), float(range_max))
        else:
            self.__storage_valid = 0

        self.__labels = labels
        self.__enums = []
        self.__enums_count = enums_count

        for enum in enums:
            for key, value in enum.items():
                dictionary = {
                    'label': value,
                    'value': int(key)
                }
                self.__enums.append(dictionary)

        self.__cat_id = cat_id
        self.__scat_id = scat_id

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
            return self.__storage
        elif self.dtype == REG_DTYPE.U8:
            return self.__storage
        if self.dtype == REG_DTYPE.S16:
            return self.__storage
        elif self.dtype == REG_DTYPE.U16:
            return self.__storage
        if self.dtype == REG_DTYPE.S32:
            return self.__storage
        elif self.dtype == REG_DTYPE.U32:
            return self.__storage
        if self.dtype == REG_DTYPE.S64:
            return self.__storage
        elif self.dtype == REG_DTYPE.U64:
            return self.__storage
        elif self.dtype == REG_DTYPE.FLOAT:
            return self.__storage
        else:
            return None

    @storage.setter
    def storage(self, value):
        self.__storage = value

    @property
    def storage_valid(self):
        """ int: If storage is valid """
        return self.__storage_valid

    @storage_valid.setter
    def storage_valid(self, value):
        self.__storage_valid = value

    @property
    def range(self):
        """ tuple: Register range (min, max), None if undefined. """
        if self.__range:
            return self.__range[0], self.__range[1]
        return None

    @property
    def labels(self):
        """ LabelsDictionary: Labels dictionary. """
        return self.__labels

    @property
    def enums(self):
        """ Enumerations list. """
        return self.__enums

    @property
    def enums_count(self):
        """ int: Register Enumerations count. """
        return self.__enums_count

    @property
    def cat_id(self):
        """ Category ID."""
        return self.__cat_id

    @property
    def scat_id(self):
        """ Sub-category ID."""
        return self.__scat_id

    @property
    def internal_use(self):
        """ int: Register internal_use. """
        return self.__internal_use
