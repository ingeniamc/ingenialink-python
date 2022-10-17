from ingenialink.dictionary import Dictionary
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

    def _read_xdf_register(self, register):
        """Reads a register from the dictionary and creates a Register instance.

        Args:
            register (Element): Register instance from the dictionary.

        """
        current_read_register = super()._read_xdf_register(register)
        if current_read_register is None:
            return None
        else:
            try:

                aux_var = int(register.attrib['address'], 16)
                current_read_register[self.AttrRegCanDict.IDX] = aux_var >> 8
                current_read_register[self.AttrRegCanDict.SUBIDX] = aux_var & 0xFF

                return current_read_register

            except KeyError as ke:
                logger.error(f"The register with the ID {current_read_register[self.AttrRegDict.IDENTIFIER]} had some "
                             f"problem because of an attribute's reading. Error caught: {ke}")
                return None

    def _add_register_list(self, register):
        """Adds the current read register into the _registers list"""
        identifier = register[self.AttrRegCanDict.IDENTIFIER]
        subnode = register[self.AttrRegCanDict.SUBNODE]

        reg = CanopenRegister(**register)

        self._registers[subnode][identifier] = reg
