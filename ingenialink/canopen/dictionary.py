from ingenialink.dictionary import Dictionary
from ingenialink.constants import SINGLE_AXIS_MINIMUM_SUBNODES
from ingenialink.canopen.register import CanopenRegister


class CanopenDictionary(Dictionary):
    """Contains all registers and information of a CANopen dictionary.

    Args:
        dictionary_path (str): Path to the Ingenia dictionary.

    """

    def __init__(self, dictionary_path):
        super().__init__(dictionary_path)
        self.version = '1'
        self.subnodes = SINGLE_AXIS_MINIMUM_SUBNODES

        self.read_dictionary()

    def read_register(self, register):
        """Reads a register from the dictionary and creates a Register instance.

        Args:
            register (Element): Register instance from the dictionary.

        """
        try:
            identifier, units, cyclic, dtype, access, subnode, \
                storage, reg_range, labels, enums, cat_id, internal_use = super().read_register(register)

            idx = int(register.attrib['address'][:6], 16)
            subidx = int("0x" + register.attrib['address'][-2:], 16)

            reg = CanopenRegister(identifier, units, cyclic, idx, subidx, dtype,
                                  access, subnode=subnode,
                                  storage=storage, reg_range=reg_range,
                                  labels=labels, enums=enums,
                                  enums_count=len(enums), cat_id=cat_id,
                                  internal_use=internal_use)
            self._registers[int(subnode)][identifier] = reg

        except Exception:
            pass
