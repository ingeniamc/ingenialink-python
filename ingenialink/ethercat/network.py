from ingenialink.network import NET_PROT


class EthercatNetwork:
    """Network for all EtherCAT communications.

    Args:
        interface_name (str): Interface name to be targeted.

    """
    def __init__(self, interface_name):
        self.interface_name = interface_name

    def load_firmware(self):
        """Loads a given firmware file to a target."""
        raise NotImplementedError

    @property
    def protocol(self):
        """NET_PROT: Obtain network protocol."""
        return NET_PROT.ECAT
