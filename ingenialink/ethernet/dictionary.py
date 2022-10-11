from ingenialink.dictionary import Dictionary, AttrRegDict
from ingenialink.constants import SINGLE_AXIS_MINIMUM_SUBNODES
from ingenialink.ethernet.register import EthernetRegister

import ingenialogger

logger = ingenialogger.get_logger(__name__)


class AttrRegEthDict(AttrRegDict):
    ADDR = 'address'


class EthernetDictionary(Dictionary):
    """Contains all registers and information of a Ethernet dictionary.

    Args:
        dictionary_path (str): Path to the Ingenia dictionary.

    """

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

            current_read_register[AttrRegEthDict.ADDR] = int(register.attrib['address'], 16)

            return current_read_register

        except KeyError as ke:
            logger.error(f'Error caught: {ke}')
            return None

    def _add_register_list(self, register):
        """Adds the current read register into the _registers list"""
        address = register[AttrRegEthDict.ADDR]
        dtype = register[AttrRegEthDict.DTYPE]
        access = register[AttrRegEthDict.ACCESS]
        identifier = register[AttrRegEthDict.IDENTIFIER]
        units = register[AttrRegEthDict.UNITS]
        cyclic = register[AttrRegEthDict.CYCLIC]
        subnode = register[AttrRegEthDict.SUBNODE]
        storage = register[AttrRegEthDict.STORAGE]
        reg_range = register[AttrRegEthDict.REG_RANGE]
        labels = register[AttrRegEthDict.LABELS]
        enums = register[AttrRegEthDict.ENUMS]
        enums_count = len(register[AttrRegEthDict.ENUMS])
        cat_id = register[AttrRegEthDict.CAT_ID]
        internal_use = register[AttrRegEthDict.INT_USE]

        reg = EthernetRegister(address, dtype, access, subnode=subnode, identifier=identifier, units=units,
                               cyclic=cyclic, storage=storage, reg_range=reg_range, labels=labels,
                               enums=enums, enums_count=enums_count, cat_id=cat_id, internal_use=internal_use)

        self._registers[subnode][identifier] = reg
