from ..network import Network, NET_PROT, NET_DEV_EVT, NET_STATE
from .servo import EthercatServo
from ingenialink.utils._utils import cstr, raise_err
from ..exceptions import *
from time import sleep
from .._ingenialink import lib, ffi


class EthercatNetwork(Network):
    def __init__(self, interface_name=""):
        super(EthercatNetwork, self).__init__()
        self.__interface_name = interface_name
        self.__cffi_network = None

    def _from_existing(self, net):
        """ Create a new class instance from an existing network.

        Args:
            net (Network): Instance to copy.

        Returns:
            Network: New instanced class.

        """
        self.__cffi_network = ffi.gc(net, lib.il_net_fake_destroy)

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
        return lib.il_net_update_firmware(self.__cffi_network,
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

        r = lib.il_servo_connect_ecat(3, _interface_name, self.__cffi_network,
                                      _servo, _dictionary, 1061,
                                      target, use_eoe_comms)
        if r <= 0:
            _servo = None
            self.__cffi_network = None
            raise_err(r)
        else:
            self.__cffi_network = ffi.cast('il_net_t *', self.__cffi_network[0])
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
        r = lib.il_net_master_stop(self.__cffi_network)
        self.__cffi_network = None
        if r < 0:
            raise ILError('Error disconnecting the drive. '
                          'Return code: {}'.format(r))

    def close_socket(self):
        """ Closes the established network socket. """
        return lib.il_net_close_socket(self.__cffi_network)

    def destroy_network(self):
        """ Destroy network instance. """
        lib.il_net_destroy(self.__cffi_network)

    def subscribe_to_network_status(self, on_evt):
        """ Calls given function everytime a connection/disconnection event is
        raised.

        Args:
            on_evt (Callback): Function that will be called every time an event
            is raised.
        """
        status = self.status
        while True:
            if status != self.status:
                if self.status == 0:
                    on_evt(NET_DEV_EVT.ADDED)
                elif self.status == 1:
                    on_evt(NET_DEV_EVT.REMOVED)
                status = self.status
            sleep(1)

    def stop_network_monitor(self):
        """ Stop monitoring network events. """
        lib.il_net_mon_stop(self.__cffi_network)

    def set_reconnection_retries(self, retries):
        """ Set the number of reconnection retries in our application.

        Args:
            retries (int): Number of reconnection retries.
        """
        return lib.il_net_set_reconnection_retries(self.__cffi_network, retries)

    def set_recv_timeout(self, timeout):
        """ Set receive communications timeout.

        Args:
            timeout (int): Timeout in ms.
        Returns:
            int: Result code.
        """
        return lib.il_net_set_recv_timeout(self.__cffi_network, timeout)

    def set_status_check_stop(self, stop):
        """ Start/Stop the internal monitor of the drive status.

        Args:
            stop (int): 0 to START, 1 to STOP.
        Returns:
            int: Result code.
        """
        return lib.il_net_set_status_check_stop(self.__cffi_network, stop)

    @property
    def protocol(self):
        """ NET_PROT: Obtain network protocol. """
        return NET_PROT.ECAT

    @property
    def _cffi_network(self):
        """ Obtain network CFFI instance. """
        return self.__cffi_network

    @_cffi_network.setter
    def _cffi_network(self, value):
        """ Set network CFFI instance. """
        self.__cffi_network = value

    @property
    def state(self):
        """ Obtain network state.

        Returns:
            str: Current network state.
        """
        return NET_STATE(lib.il_net_state_get(self.__cffi_network))

    @property
    def status(self):
        """ Obtain network status.

        Returns:
            str: Current network status.
        """
        return lib.il_net_status_get(self.__cffi_network)

    @property
    def interface_name(self):
        return self.__interface_name

    @interface_name.setter
    def interface_name(self, value):
        self.__interface_name = value






