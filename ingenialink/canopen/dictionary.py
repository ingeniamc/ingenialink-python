import ingenialogger

from ingenialink.dictionary import Dictionary
from ingenialink.canopen.register import CanopenRegister

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
        current_read_register = super()._read_xdf_register(register)
        if current_read_register is None:
            return None
        try:
            aux_var = int(register.attrib['address'], 16)
            current_read_register[self.AttrRegCanDict.IDX] = aux_var >> 8
            current_read_register[self.AttrRegCanDict.SUBIDX] = aux_var & 0xFF

            return current_read_register

        except KeyError as ke:
            logger.error(f"Register with ID {current_read_register[self.AttrRegCanDict.IDENTIFIER]} has not attribute {ke}")
            return None

    def _add_register_list(self, register):
        identifier = register[self.AttrRegCanDict.IDENTIFIER]
        subnode = register[self.AttrRegCanDict.SUBNODE]

        reg = CanopenRegister(**register)

        self._registers[subnode][identifier] = reg
