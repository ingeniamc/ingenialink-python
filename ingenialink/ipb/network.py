from ingenialink.network import Network, NET_DEV_EVT, NET_STATE
from .._ingenialink import lib, ffi
from abc import ABC, abstractmethod
from time import sleep

import ingenialogger
logger = ingenialogger.get_logger(__name__)


class IPBNetwork(Network, ABC):
    """IPB Network defines a general class for all IPB based communications."""
    def __init__(self):
        super(IPBNetwork, self).__init__()
        self._cffi_network = None
        """CFFI instance of the network."""

    def _from_existing(self, net):
        """Create a new class instance from an existing network.

        Args:
            net (Network): Instance to copy.

        """
        self._cffi_network = ffi.gc(net, lib.il_net_fake_destroy)

    @abstractmethod
    def scan_slaves(self):
        raise NotImplementedError

    @abstractmethod
    def connect_to_slave(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def disconnect_from_slave(self, servo):
        raise NotImplementedError

    @abstractmethod
    def load_firmware(self, *args, **kwargs):
        raise NotImplementedError

    def close_socket(self):
        """Closes the established network socket."""
        return lib.il_net_close_socket(self._cffi_network)

    def destroy_network(self):
        """Destroy network instance."""
        lib.il_net_destroy(self._cffi_network)

    def subscribe_to_status(self, callback):
        """Calls given function everytime a connection/disconnection event is
        raised.

        Args:
            callback (Callback): Function that will be called every time an event
            is raised.

        """
        # TODO: Re-implement using observers and internal threads
        status = self.status
        while True:
            if status != self.status:
                if self.status == 0:
                    callback(NET_DEV_EVT.ADDED)
                elif self.status == 1:
                    callback(NET_DEV_EVT.REMOVED)
                status = self.status
            sleep(1)

    def unsubscribe_from_status(self, callback):
        # TODO: Re-implement using observers and internal threads
        raise NotImplementedError

    def stop_network_monitor(self):
        """Stop monitoring network events."""
        lib.il_net_mon_stop(self._cffi_network)

    def set_reconnection_retries(self, retries):
        """Set the number of reconnection retries in our application.

        Args:
            retries (int): Number of reconnection retries.

        """
        return lib.il_net_set_reconnection_retries(self._cffi_network, retries)

    def set_recv_timeout(self, timeout):
        """Set receive communications timeout.

        Args:
            timeout (int): Timeout in ms.
        Returns:
            int: Result code.

        """
        return lib.il_net_set_recv_timeout(self._cffi_network, timeout)

    def set_status_check_stop(self, stop):
        """Start/Stop the internal monitor of the drive status.

        Args:
            stop (int): 0 to START, 1 to STOP.
        Returns:
            int: Result code.

        """
        return lib.il_net_set_status_check_stop(self._cffi_network, stop)

    @property
    def protocol(self):
        raise NotImplementedError

    @property
    def state(self):
        """Obtain network state.

        Returns:
            str: Current network state.

        """
        return NET_STATE(lib.il_net_state_get(self._cffi_network))

    @property
    def status(self):
        """Obtain network status.

        Returns:
            str: Current network status.

        """
        return lib.il_net_status_get(self._cffi_network)
