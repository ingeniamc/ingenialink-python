from time import sleep
from threading import Thread
from abc import ABC, abstractmethod
from enum import Enum
from .._ingenialink import lib, ffi
from ingenialink.exceptions import ILError
from ingenialink.utils._utils import pstr, raise_err, raise_null

import ingenialogger
logger = ingenialogger.get_logger(__name__)


class NET_PROT(Enum):
    """Network Protocol."""
    EUSB = lib.IL_NET_PROT_EUSB
    MCB = lib.IL_NET_PROT_MCB
    ETH = lib.IL_NET_PROT_ETH
    ECAT = lib.IL_NET_PROT_ECAT
    CAN = 5


class NET_STATE(Enum):
    """Network State."""
    CONNECTED = lib.IL_NET_STATE_CONNECTED
    DISCONNECTED = lib.IL_NET_STATE_DISCONNECTED
    FAULTY = lib.IL_NET_STATE_FAULTY


class NET_DEV_EVT(Enum):
    """Device Event."""
    ADDED = lib.IL_NET_DEV_EVT_ADDED
    REMOVED = lib.IL_NET_DEV_EVT_REMOVED

@ffi.def_extern()
def _on_found_cb(ctx, servo_id):
    """On found callback shim."""
    self = ffi.from_handle(ctx)
    self._on_found(int(servo_id))


@ffi.def_extern()
def _on_evt_cb(ctx, evt, port):
    """On event callback shim."""
    self = ffi.from_handle(ctx)
    self._on_evt(NET_DEV_EVT(evt), pstr(port))

class NetStatusListener(Thread):
    """Network status listener thread to check if the drive is alive.

    Args:
        network (IPBNetwork): Network instance of the IPB communication.

    """

    def __init__(self, network):
        super(NetStatusListener, self).__init__()
        self.__net = network
        self.__stop = False

    def run(self):
        status = self.__net.status
        while not self.__stop:
            if status != self.__net.status:
                if self.__net.status == NET_STATE.CONNECTED.value:
                    self.__net._notify_status(NET_DEV_EVT.ADDED)
                elif self.__net.status == NET_STATE.DISCONNECTED.value:
                    self.__net._notify_status(NET_DEV_EVT.REMOVED)
                status = self.__net.status
            sleep(1)

    def stop(self):
        self.__stop = True


class IPBNetwork(ABC):
    """IPB Network defines a general class for all IPB based communications."""
    def __init__(self):
        super(IPBNetwork, self).__init__()
        self._cffi_network = None
        """CFFI instance of the network."""

        self.__observers_net_state = []
        self.__listener_net_status = None

    def _create_cffi_network(self, cffi_network):
        """Create a new class instance from an existing network.

        Args:
            cffi_network (CData): Instance to copy.

        """
        self._cffi_network = ffi.gc(cffi_network, lib.il_net_fake_destroy)

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
            callback (function): Function that will be called every time an event
                is raised.

        """
        if callback in self.__observers_net_state:
            logger.info('Callback already subscribed.')
            return
        self.__observers_net_state.append(callback)

    def unsubscribe_from_status(self, callback):
        """Unsubscribe from state changes.

        Args:
            callback (function): Callback function.

        """
        if callback not in self.__observers_net_state:
            logger.info('Callback not subscribed.')
            return
        self.__observers_net_state.remove(callback)

    def _notify_status(self, status):
        for callback in self.__observers_net_state:
            callback(status)

    def _set_status_check_stop(self, stop):
        """Start/Stop the internal monitor of the drive status.

        Args:
            stop (int): 0 to START, 1 to STOP.

        Raises:
            ILError: If the operation returns a negative error code.

        """
        r = lib.il_net_set_status_check_stop(self._cffi_network, stop)

        if r < 0:
            raise ILError('Could not start servo monitoring')

    def start_status_listener(self):
        """Start monitoring network events (CONNECTION/DISCONNECTION)."""
        self._set_status_check_stop(0)
        if not self.__listener_net_status:
            self.__listener_net_status = NetStatusListener(self)
            self.__listener_net_status.start()

    def stop_status_listener(self):
        """Stop monitoring network events (CONNECTION/DISCONNECTION)."""
        self._set_status_check_stop(1)
        if self.__listener_net_status is not None and \
                self.__listener_net_status.is_alive():
            self.__listener_net_status.stop()
            self.__listener_net_status.join()
        self.__listener_net_status = None

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
        return lib.il_net_set_recv_timeout(self._cffi_network, timeout*1000)

    @property
    def protocol(self):
        raise NotImplementedError

    @property
    def status(self):
        """NET_STATE: Obtain network status"""
        return lib.il_net_status_get(self._cffi_network)


class NetworkMonitor:
    """Network Monitor.

    Args:
        prot (NET_PROT): Protocol.

    Raises:
        TypeError: If the protocol type is invalid.
        ILCreationError: If the monitor cannot be created.

    """
    def __init__(self, prot):
        if not isinstance(prot, NET_PROT):
            raise TypeError('Invalid protocol')

        mon = lib.il_net_dev_mon_create(prot.value)
        raise_null(mon)

        self._mon = ffi.gc(mon, lib.il_net_dev_mon_destroy)

    def start(self, on_evt):
        """Start the monitor.

        Args:
            on_evt (callback): Callback function.

        """
        self._on_evt = on_evt
        self._handle = ffi.new_handle(self)

        r = lib.il_net_dev_mon_start(self._mon, lib._on_evt_cb, self._handle)
        raise_err(r)

    def stop(self):
        """Stop the monitor."""
        lib.il_net_dev_mon_stop(self._mon)
