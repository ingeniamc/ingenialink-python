from ..network import NET_PROT
from .servo import EthercatServo
from ..ipb_network import IPBNetwork
from ingenialink.utils._utils import cstr, raise_err
from ..exceptions import *
from .._ingenialink import lib, ffi


class EthercatNetwork(IPBNetwork):
    """ Network for all EtherCAT communications.

    Args:
        interface_name (str): Interface name to be targeted.
    """
    def __init__(self, interface_name=""):
        super(EthercatNetwork, self).__init__()
        self.__interface_name = interface_name
        self._cffi_network = None

    def load_firmware(self, fw_file, target=1, boot_in_app=True):
        """ Loads a given firmware file to a target.

        Args:
            target (int): Targeted node ID to be loaded.
            fw_file (str): Path to the firmware file.
            boot_in_app (bool): If summit series -> True.
                                If capitan series -> False.
                                If custom device -> Contact manufacturer.

        Raises:
            ILFirmwareLoadError: The firmware load process fails
            with an error message.
        """
        _interface_name = cstr(self.__interface_name) \
            if self.__interface_name else ffi.NULL
        _fw_file = cstr(fw_file) if fw_file else ffi.NULL
        return lib.il_net_update_firmware(self._cffi_network,
                                          _interface_name,
                                          target,
                                          _fw_file,
                                          boot_in_app)

    def scan_slaves(self):
        """ Scan all the slaves connected in the network.

        Returns:
            list: List of number of slaves connected to the network.
        """
        _interface_name = cstr(self.__interface_name) \
            if self.__interface_name else ffi.NULL

        number_slaves = lib.il_net_num_slaves_get(_interface_name)
        slaves = []
        for slave in range(1, number_slaves):
            slaves.append(slave)
        return slaves

    def connect_to_slave(self, target=1, dictionary="", use_eoe_comms=1):
        """ Connect a slave through an EtherCAT connection.

        Args:
            target (int): Number of the target slave.
            dictionary (str): Path to the dictionary to be loaded.
            use_eoe_comms (int): Specify which architecture is the target based on.

        Returns:
            EthercatServo: Instance of the connected servo.
        """
        servo = None
        _interface_name = cstr(self.__interface_name) \
            if self.__interface_name else ffi.NULL
        _dictionary = cstr(dictionary) if dictionary else ffi.NULL

        _servo = ffi.new('il_servo_t **')

        r = lib.il_servo_connect_ecat(3, _interface_name, self._cffi_network,
                                      _servo, _dictionary, 1061,
                                      target, use_eoe_comms)
        if r <= 0:
            _servo = None
            self._cffi_network = None
            raise_err(r)
        else:
            self._cffi_network = ffi.cast('il_net_t *', self._cffi_network[0])
            servo = EthercatServo._from_existing(_servo, _dictionary)
            servo._servo = ffi.cast('il_servo_t *', servo._servo[0])
            servo.net = self
            self.servos.append(servo)

        return servo

    def disconnect_from_slave(self, servo):
        """ Disconnects the slave from the network.

        Args:
            servo (EthernetServo): Instance of the servo connected.
        """
        # TODO: This stops all connections no only the target servo.
        if servo in self.servos:
            self.servos.remove(servo)
        r = lib.il_net_master_stop(self._cffi_network)
        self.destroy_network()
        self._cffi_network = None
        if r < 0:
            raise ILError('Error disconnecting the drive. '
                          'Return code: {}'.format(r))

    @property
    def protocol(self):
        """ NET_PROT: Obtain network protocol. """
        return NET_PROT.ECAT

    @property
    def interface_name(self):
        return self.__interface_name

    @interface_name.setter
    def interface_name(self, value):
        self.__interface_name = value






