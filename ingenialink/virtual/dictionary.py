from typing import Optional
from xml.etree import ElementTree

import ingenialogger

from ingenialink.dictionary import Interface
from ingenialink.ethernet.dictionary import EthernetDictionaryV2
from ingenialink.ethernet.register import EthernetRegister

logger = ingenialogger.get_logger(__name__)


class VirtualDictionary(EthernetDictionaryV2):
    """Contains all registers and information of a dictionary compatible with the virtual drive.

    It adapts a canopen dictionary to work in the ethernet communication used for the virtual drive.

    Args:
        dictionary_path: Path to the Ingenia dictionary.

    """

    interface = Interface.VIRTUAL

    def _transform_canopen_index_to_mcb_address(self, index: int, subnode: int) -> int:
        """Transfrom CANopen index to MCB address.

        CANopen index is an uint16 but MCB address only has 12 bits, so,
        some index makes overflow in MCB frame.

        Args:
            index: CANopen index
            subnode: register subnode

        Returns:
            MCB address

        """
        return index - (0x2000 + (0x800 * (subnode - 1)))

    def _read_xdf_register(self, register: ElementTree.Element) -> Optional[EthernetRegister]:
        current_read_register = super()._read_xdf_register(register)

        if current_read_register is None:
            return None

        if self.dict_interface == "CAN" and (
            register.attrib["cat_id"] == "CIA402" or register.attrib["id"].startswith("CIA402_")
        ):
            return None

        if current_read_register.identifier in ["MON_DATA_VALUE", "DIST_DATA_VALUE"]:
            return None

        try:
            if self.dict_interface == "CAN":
                reg_address = int(register.attrib["address"][:6], 16)
                if current_read_register.subnode > 0:
                    reg_address = self._transform_canopen_index_to_mcb_address(
                        reg_address, current_read_register.subnode
                    )
                else:
                    reg_address -= 0x5800
            else:
                reg_address = int(register.attrib["address"], 16)

            ethernet_register = EthernetRegister(
                reg_address,
                current_read_register.dtype,
                current_read_register.access,
                identifier=current_read_register.identifier,
                units=current_read_register.units,
                pdo_access=current_read_register.pdo_access,
                phy=current_read_register.phy,
                subnode=current_read_register.subnode,
                storage=current_read_register.storage,
                reg_range=current_read_register.range,
                labels=current_read_register.labels,
                enums=current_read_register.enums,
                cat_id=current_read_register.cat_id,
                scat_id=current_read_register.scat_id,
                internal_use=current_read_register.internal_use,
                address_type=current_read_register.address_type,
                bitfields=current_read_register.bitfields,
                monitoring=current_read_register.monitoring,
                description=current_read_register.description,
            )

            return ethernet_register

        except KeyError as ke:
            logger.error(
                f"Register with ID {current_read_register.identifier} has not attribute {ke}"
            )
            return None
