from ingenialink.dictionary import Dictionary
from ingenialink.ethernet.register import EthernetRegister

import ingenialogger

logger = ingenialogger.get_logger(__name__)


class EthernetDictionary(Dictionary):
    """Contains all registers and information of a Ethernet dictionary.

    Args:
        dictionary_path (str): Path to the Ingenia dictionary.

    """

    class AttrRegEthDict(Dictionary.AttrRegDict):
        ADDR = "address"

    def __init__(self, dictionary_path):
        super().__init__(dictionary_path)

    def _read_xdf_register(self, register):
        current_read_register = super()._read_xdf_register(register)
        if current_read_register is None:
            return None
        try:
            current_read_register[self.AttrRegEthDict.ADDR] = int(register.attrib["address"], 16)

            return current_read_register

        except KeyError as ke:
            logger.error(
                f"Register with ID {current_read_register[self.AttrRegDict.IDENTIFIER]} has not"
                f" attribute {ke}"
            )
            return None

    def _add_register_list(self, register):
        identifier = register[self.AttrRegEthDict.IDENTIFIER]
        subnode = register[self.AttrRegEthDict.SUBNODE]

        reg = EthernetRegister(**register)

        self._registers[subnode][identifier] = reg
