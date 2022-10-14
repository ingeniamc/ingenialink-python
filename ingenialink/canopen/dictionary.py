from ingenialink.dictionary import Dictionary, AttrRegDict
from ingenialink.canopen.register import CanopenRegister

import ingenialogger

logger = ingenialogger.get_logger(__name__)


class AttrRegCanDict(AttrRegDict):
    IDX = 'idx'
    SUBIDX = 'subidx'


class CanopenDictionary(Dictionary):
    """Contains all registers and information of a CANopen dictionary.

    Args:
        dictionary_path (str): Path to the Ingenia dictionary.

    """

    def __init__(self, dictionary_path):
        super().__init__(dictionary_path)

    def _read_xdf_register(self, register):
        """Reads a register from the dictionary and creates a Register instance.

        Args:
            register (Element): Register instance from the dictionary.

        """
        try:
            current_read_register = super()._read_xdf_register(register)

            current_read_register[AttrRegCanDict.IDX] = int(register.attrib['address'][:6], 16)
            current_read_register[AttrRegCanDict.SUBIDX] = int("0x" + register.attrib['address'][-2:], 16)

            return current_read_register

        except KeyError as ke:
            logger.error(f'Error caught: {ke}')
            return None

    def _add_register_list(self, register):
        """Adds the current read register into the _registers list"""
        identifier = register[AttrRegCanDict.IDENTIFIER]
        units = register[AttrRegCanDict.UNITS]
        cyclic = register[AttrRegCanDict.CYCLIC]
        idx = register[AttrRegCanDict.IDX]
        subidx = register[AttrRegCanDict.SUBIDX]
        dtype = register[AttrRegCanDict.DTYPE]
        access = register[AttrRegCanDict.ACCESS]
        subnode = register[AttrRegCanDict.SUBNODE]
        storage = register[AttrRegCanDict.STORAGE]
        reg_range = register[AttrRegCanDict.REG_RANGE]
        labels = register[AttrRegCanDict.LABELS]
        enums = register[AttrRegCanDict.ENUMS]
        enums_count = len(register[AttrRegCanDict.ENUMS])
        cat_id = register[AttrRegCanDict.CAT_ID]
        internal_use = register[AttrRegCanDict.INT_USE]

        reg = CanopenRegister(identifier, units, cyclic, idx, subidx, dtype,
                              access, subnode=subnode, storage=storage, reg_range=reg_range,
                              labels=labels, enums=enums, enums_count=enums_count, cat_id=cat_id,
                              internal_use=internal_use)

        self._registers[subnode][identifier] = reg
