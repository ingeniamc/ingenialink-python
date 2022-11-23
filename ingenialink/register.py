from ingenialink import exceptions as exc
from ingenialink.enums.register import REG_DTYPE, REG_ACCESS, REG_PHY

from abc import ABC

# CANOPEN DTYPES
IL_REG_DTYPE_DOMAIN = 15

dtypes_ranges = {
    REG_DTYPE.U8: {"max": 255, "min": 0},
    REG_DTYPE.S8: {"max": 127, "min": -128},
    REG_DTYPE.U16: {"max": 65535, "min": 0},
    REG_DTYPE.S16: {"max": 32767, "min": -32767 - 1},
    REG_DTYPE.U32: {"max": 4294967295, "min": 0},
    REG_DTYPE.S32: {"max": 2147483647, "min": -2147483647 - 1},
    REG_DTYPE.U64: {"max": 18446744073709551615, "min": 0},
    REG_DTYPE.S64: {"max": 9223372036854775807, "min":  9223372036854775807 - 1},
    REG_DTYPE.FLOAT: {"max": 2147483647, "min": -2147483647 - 1}
}


class Register(ABC):
    """Register Base class.

        Args:
            dtype (REG_DTYPE): Data type.
            access (REG_ACCESS): Access type.
            identifier (str, optional): Identifier.
            units (str, optional): Units.
            cyclic (str, optional): Cyclic typed register.
            phy (REG_PHY, optional): Physical units.
            subnode (int): Subnode.
            storage (any, optional): Storage.
            reg_range (tuple, optional): Range (min, max).
            labels (dict, optional): Register labels.
            enums (dict): Enumeration registers.
            enums_count (int): Number of enumeration registers.
            cat_id (str, optional): Category ID.
            scat_id (str, optional): Sub-category ID.
            internal_use (int, optional): Internal use.

        Raises:
            TypeError: If any of the parameters has invalid type.
            ILValueError: If the register is invalid.
            ILAccessError: Register with wrong access type.

        """

    def __init__(self, dtype, access, identifier=None, units=None, cyclic="CONFIG",
                 phy=REG_PHY.NONE, subnode=1, storage=None, reg_range=(None, None),
                 labels=None, enums=None, cat_id=None, scat_id=None, internal_use=0):

        if labels is None:
            labels = {}
        if enums is None:
            enums = {}

        self.__type_errors(dtype, access, phy)

        self._dtype = dtype.value
        self._access = access.value
        self._identifier = identifier
        self._units = units
        self._cyclic = cyclic
        self._phy = phy.value
        self._subnode = subnode
        self._storage = storage
        self._range = (None, None) if not reg_range else reg_range
        self._labels = labels
        self._enums = enums
        self._enums_count = len(enums)
        self._cat_id = cat_id
        self._scat_id = scat_id
        self._internal_use = internal_use
        self._storage_valid = 0 if not storage else 1

        self.__config_range(reg_range)
        self._enums = self.__config_enums()

    def __type_errors(self, dtype, access, phy):
        if not isinstance(dtype, REG_DTYPE):
            raise exc.ILValueError('Invalid data type')

        if not isinstance(access, REG_ACCESS):
            raise exc.ILAccessError('Invalid access type')

        if not isinstance(phy, REG_PHY):
            raise exc.ILValueError('Invalid physical units type')

    def __config_range(self, reg_range):
        if self.dtype in dtypes_ranges:
            if self.dtype == REG_DTYPE.FLOAT:
                if self.storage:
                    self._storage = float(self.storage)
                aux_range = (
                    float(reg_range[0]) if reg_range[0] else dtypes_ranges[self.dtype]["min"],
                    float(reg_range[1]) if reg_range[1] else dtypes_ranges[self.dtype]["max"],
                )
            else:
                if self.storage:
                    self._storage = int(self.storage)
                aux_range = (
                    int(reg_range[0]) if reg_range[0] else dtypes_ranges[self.dtype]["min"],
                    int(reg_range[1]) if reg_range[1] else dtypes_ranges[self.dtype]["max"],
                )
            self._range = aux_range
        else:
            self._storage_valid = 0

    def __config_enums(self):
        aux_enums = []
        for key, value in self._enums.items():
            dictionary = {
                'label': value,
                'value': int(key)
            }
            aux_enums.append(dictionary)

        return aux_enums

    @property
    def dtype(self):
        """REG_DTYPE: Data type of the register."""
        return REG_DTYPE(self._dtype)

    @property
    def access(self):
        """REG_ACCESS: Access type of the register."""
        return REG_ACCESS(self._access)

    @property
    def identifier(self):
        """str: Register identifier."""
        return self._identifier

    @property
    def units(self):
        """str: Units of the register."""
        return self._units

    @property
    def cyclic(self):
        """str: Defines if the register is cyclic."""
        return self._cyclic

    @property
    def phy(self):
        """REG_PHY: Physical units of the register."""
        return REG_PHY(self._phy)

    @property
    def subnode(self):
        """int: Target subnode of the register."""
        return self._subnode

    @property
    def storage(self):
        """any: Defines if the register needs to be stored."""
        if not self.storage_valid:
            return None

        if self.dtype in [REG_DTYPE.S8, REG_DTYPE.U8, REG_DTYPE.S16,
                          REG_DTYPE.U16, REG_DTYPE.S32, REG_DTYPE.U32,
                          REG_DTYPE.S64, REG_DTYPE.U64, REG_DTYPE.FLOAT]:
            return self._storage
        else:
            return None

    @storage.setter
    def storage(self, value):
        """any: Defines if the register needs to be stored."""
        self._storage = value

    @property
    def storage_valid(self):
        """bool: Defines if the register storage is valid."""
        return self._storage_valid

    @storage_valid.setter
    def storage_valid(self, value):
        """bool: Defines if the register storage is valid."""
        self._storage_valid = value

    @property
    def range(self):
        """tuple: Containing the minimum and the maximum values of the register."""
        if self._range:
            return self._range[0], self._range[1]
        return None

    @property
    def labels(self):
        """dict: Containing the labels of the register."""
        return self._labels

    @property
    def enums(self):
        """dict: Containing all the enums for the register."""
        if not hasattr(self, '_enums'):
            self._enums = []
            for i in range(0, self.enums_count):
                aux_dict = {
                    'label': self._enums[i].label,
                    'value': self._enums[i].value
                }
                self._enums.append(aux_dict)
        return self._enums

    @property
    def enums_count(self):
        """int: The number of the enums in the register."""
        return self._enums_count

    @property
    def cat_id(self):
        """str: Category ID"""
        return self._cat_id

    @property
    def scat_id(self):
        """str: Sub-Category ID"""
        return self._scat_id

    @property
    def internal_use(self):
        """int: Defines if the register is only for internal uses."""
        return self._internal_use
