from ingenialink.dictionary import Dictionary
from ingenialink.constants import SINGLE_AXIS_MINIMUM_SUBNODES
from ingenialink.canopen.register import CanopenRegister
import ingenialogger

logger = ingenialogger.get_logger(__name__)


class CanopenDictionary(Dictionary):
    """Contains all registers and information of a CANopen dictionary.

    Args:
        dictionary_path (str): Path to the Ingenia dictionary.

    """

    class AttrRegCanDict(Dictionary.AttrRegDict):
        IDX = 'idx'
        SUBIDX = 'subidx'

    def __init__(self, dictionary_path):
        super().__init__(dictionary_path)
        self.version = '1'
        self.subnodes = SINGLE_AXIS_MINIMUM_SUBNODES

        self.read_dictionary()

    def _read_register(self, register):
        """Reads a register from the dictionary and creates a Register instance.

        Args:
            register (Element): Register instance from the dictionary.

        """
        try:
            current_read_register = super()._read_register(register)
            aux_var = int(register.attrib['address'], 16)
            current_read_register[self.AttrRegCanDict.IDX] = aux_var >> 8
            current_read_register[self.AttrRegCanDict.SUBIDX] = aux_var & 0xFF

            return current_read_register

        except KeyError as ke:
            logger.error(f'Error caught: {ke}')
            return None

    def _add_register_list(self, register):
        """Adds the current read register into the _registers list"""
        identifier = register[self.AttrRegCanDict.IDENTIFIER]
        units = register[self.AttrRegCanDict.UNITS]
        cyclic = register[self.AttrRegCanDict.CYCLIC]
        idx = register[self.AttrRegCanDict.IDX]
        subidx = register[self.AttrRegCanDict.SUBIDX]
        dtype = register[self.AttrRegCanDict.DTYPE]
        access = register[self.AttrRegCanDict.ACCESS]
        subnode = register[self.AttrRegCanDict.SUBNODE]
        storage = register[self.AttrRegCanDict.STORAGE]
        reg_range = register[self.AttrRegCanDict.REG_RANGE]
        labels = register[self.AttrRegCanDict.LABELS]
        enums = register[self.AttrRegCanDict.ENUMS]
        enums_count = len(register[self.AttrRegCanDict.ENUMS])
        cat_id = register[self.AttrRegCanDict.CAT_ID]
        internal_use = register[self.AttrRegCanDict.DESC]

        reg = CanopenRegister(identifier, units, cyclic, idx, subidx, dtype,
                              access, subnode=subnode, storage=storage, reg_range=reg_range,
                              labels=labels, enums=enums, enums_count=enums_count, cat_id=cat_id,
                              internal_use=internal_use)

        self._registers[subnode][identifier] = reg
