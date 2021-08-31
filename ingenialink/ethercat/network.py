from ..network import NET_PROT
from .servo import EthercatServo
from ingenialink.ipb.network import IPBNetwork
from ingenialink.utils._utils import cstr, raise_err
from ..exceptions import *
from .._ingenialink import lib, ffi


class EthercatNetwork(IPBNetwork):
    """Network for all EtherCAT communications.

    Args:
        interface_name (str): Interface name to be targeted.

    """
    def __init__(self, interface_name=""):
        super(EthercatNetwork, self).__init__()
        self._cffi_network = ffi.new('il_net_t **')
        self.interface_name = interface_name
        """str: Interface name used in the network settings."""

    def load_firmware(self, fw_file, target=1, boot_in_app=True):
        """Loads a given firmware file to a target.

        .. warning::
            Choose the ``boot_in_app`` flag accordingly to your
            servo specifications otherwise the servo could enter
            a blocking state.

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
        try:
            _interface_name = cstr(self.interface_name) \
                if self.interface_name else ffi.NULL
            _fw_file = cstr(fw_file) if fw_file else ffi.NULL
            r = lib.il_net_update_firmware(self._cffi_network,
                                           _interface_name,
                                           target,
                                           _fw_file,
                                           boot_in_app)
            if r < 0:
                raise ILFirmwareLoadError('Error updating firmware. '
                                          'Error code: {}'.format(r))
        except Exception as e:
            raise ILFirmwareLoadError(e)

    def scan_slaves(self):
        """Scan all the slaves connected in the network.

        Returns:
            list: List of number of slaves connected to the network.

        """
        _interface_name = cstr(self.interface_name) \
            if self.interface_name else ffi.NULL

        number_slaves = lib.il_net_num_slaves_get(_interface_name)
        slaves = []
        for slave in range(number_slaves):
            slaves.append(slave + 1)
        return slaves

    def connect_to_slave(self, target=1, dictionary="", use_eoe_comms=1):
        """Connect a slave through an EtherCAT connection.

        Args:
            target (int): Number of the target slave.
            dictionary (str): Path to the dictionary to be loaded.
            use_eoe_comms (int): Specify which architecture is the target based on.

        Returns:
            EthercatServo: Instance of the connected servo.

        """
        servo = None
        _interface_name = cstr(self.interface_name) \
            if self.interface_name else ffi.NULL
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
            net_ = ffi.cast('il_net_t *', self._cffi_network[0])
            servo_ = ffi.cast('il_servo_t *', _servo[0])
            servo = EthercatServo(servo_, net_, target, dictionary)
            self._cffi_network = net_
            self.servos.append(servo)

        return servo

    def disconnect_from_slave(self, servo):
        """Disconnects the slave from the network.

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
        """NET_PROT: Obtain network protocol."""
        return NET_PROT.ECAT
