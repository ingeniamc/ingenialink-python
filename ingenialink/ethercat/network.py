import os
import sys
import platform
import subprocess
import inspect
import time
from collections import defaultdict
from typing import Optional, Callable
from threading import Thread

import ingenialogger
import pysoem

from ingenialink.network import Network, NET_PROT, NET_STATE, NET_DEV_EVT
from ingenialink.exceptions import ILFirmwareLoadError, ILError
from ingenialink import bin as bin_module
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.constants import DEFAULT_ECAT_CONNECTION_TIMEOUT

logger = ingenialogger.get_logger(__name__)


class NetStatusListener(Thread):
    """Network status listener thread to check if the drive is alive.

    Args:
        network: Network instance of the EtherCAT communication.

    """

    def __init__(self, network: "EthercatNetwork", refresh_time=0.25):
        super(NetStatusListener, self).__init__()
        self.__network = network
        self.__refresh_time = refresh_time
        self.__stop = False
        self._ecat_master = self.__network._ecat_master

    def run(self):
        while not self.__stop:
            self._ecat_master.read_state()
            for servo in self.__network.servos:
                slave_id = servo.slave_id
                servo_state = self.__network._get_servo_state(slave_id)
                slave_is_alive = servo.slave.state == pysoem.NONE_STATE
                if servo_state == NET_STATE.CONNECTED and slave_is_alive:
                    self.__network._notify_status(slave_id, NET_DEV_EVT.REMOVED)
                    self.__network._set_servo_state(slave_id, NET_STATE.DISCONNECTED)
                if servo_state == NET_STATE.DISCONNECTED and not slave_is_alive:
                    self.__network._notify_status(slave_id, NET_DEV_EVT.ADDED)
                    self.__network._set_servo_state(slave_id, NET_STATE.CONNECTED)
                time.sleep(self.__refresh_time)

    def stop(self):
        self.__stop = True


class EthercatNetwork(Network):
    """Network for all EtherCAT communications.

    Args:
        interface_name: Interface name to be targeted.
        connection_timeout: Time in seconds of the connection timeout.

    """

    FOE_APPLICATION = {"win32": {"64bit": "FoE/win_64x/FoEUpdateFirmware.exe"}}
    FOE_ERRORS = {
        1: "Can’t read the input file.",
        2: "ECAT slave can’t reach the BOOT mode.",
        3: "No ECAT slave detected",
        4: "Can’t initialize the network adapter",
        5: "Drive can't init. Ensure the FW file is right",
    }
    UNKNOWN_FOE_ERROR = "Unknown error"

    def __init__(
        self, interface_name: str, connection_timeout: float = DEFAULT_ECAT_CONNECTION_TIMEOUT
    ):
        super(EthercatNetwork, self).__init__()
        self.interface_name: str = interface_name
        self.servos: list = []
        self.__servos_state: dict[int, NET_STATE] = {}
        self.__listener_net_status: Optional[NetStatusListener] = None
        self.__observers_net_state: dict[int, list] = defaultdict(list)
        self._ecat_master: pysoem.CdefMaster = pysoem.Master()
        self._ecat_master.open(self.interface_name)
        self._ecat_master.sdo_read_timeout = int(1_000_000 * connection_timeout)
        self._ecat_master.sdo_write_timeout = int(1_000_000 * connection_timeout)

    def scan_slaves(self) -> list[int]:
        """Scans for nodes in the network.

        Returns:
            List containing all the detected node IDs.

        """
        nodes = self._ecat_master.config_init()
        return list(range(1, nodes + 1))

    def connect_to_slave(
        self,
        slave_id: int,
        dictionary: Optional[str] = None,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ) -> EthercatServo:
        """Connects to a drive through a given slave number.

        Args:
            slave_id: Targeted slave to be connected.
            dictionary: Path to the dictionary file.
            servo_status_listener: Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener: Toggle the listener of the network
                status, connection and disconnection.

        Raises:
            ILError: If the slave ID is not valid.
            ILError: If no slaves are found.

        """
        if not isinstance(slave_id, int) or slave_id < 0:
            raise ILError("Invalid slave ID value")
        slaves = self.scan_slaves()
        if len(slaves) == 0:
            raise ILError("Could not find any slaves in the network.")
        if slave_id not in slaves:
            raise (ILError(f"Slave {slave} was not found."))
        slave = self._ecat_master.slaves[slave_id]
        servo = EthercatServo(slave, slave_id, dictionary, servo_status_listener)
        self.servos.append(servo)
        self._set_servo_state(slave_id, NET_STATE.CONNECTED)
        if net_status_listener:
            self.start_status_listener()
        return servo

    def disconnect_from_slave(self, servo: EthercatServo) -> None:
        """Disconnects the slave from the network.

        Args:
            servo: Instance of the servo connected.

        """
        self.servos.remove(servo)
        if not self.servos:
            self.stop_status_listener()
            self._ecat_master.close()

    def subscribe_to_status(self, slave_id: int, callback: Callable) -> None:
        """Subscribe to network state changes.

        Args:
            slave_id: Slave ID of the drive to subscribe.
            callback: Callback function.

        """
        if callback in self.__observers_net_state[slave_id]:
            logger.info("Callback already subscribed.")
            return
        self.__observers_net_state[slave_id].append(callback)

    def unsubscribe_from_status(self, slave_id: int, callback: Callable) -> None:
        """Unsubscribe from network state changes.

        Args:
            slave_id: Slave ID of the drive to subscribe.
            callback: Callback function.

        """
        if callback not in self.__observers_net_state[slave_id]:
            logger.info("Callback not subscribed.")
            return
        self.__observers_net_state[slave_id].remove(callback)

    def start_status_listener(self) -> None:
        """Start monitoring network events (CONNECTION/DISCONNECTION)."""
        if self.__listener_net_status is None:
            listener = NetStatusListener(self)
            listener.start()
            self.__listener_net_status = listener

    def stop_status_listener(self) -> None:
        """Stops the NetStatusListener from listening to the drive."""
        if self.__listener_net_status is not None:
            self.__listener_net_status.stop()
            self.__listener_net_status.join()
        self.__listener_net_status = None

    def load_firmware(self, fw_file, slave_id=1):
        """Loads a given firmware file to a target slave.

        Args:
            fw_file (str): Path to the firmware file.
            slave_id (int): Slave ID to which load the firmware file.

        Raises:
            FileNotFoundError: If the firmware file cannot be found.
            ILFirmwareLoadError: If no slave is detected.
            ILFirmwareLoadError: If the FoE write operation is not successful.
            NotImplementedError: If FoE is not implemented for the current OS and architecture

        """
        if not os.path.isfile(fw_file):
            raise FileNotFoundError(f"Could not find {fw_file}.")

        arch = platform.architecture()[0]
        sys_name = sys.platform
        app_path = self.FOE_APPLICATION.get(sys_name, {}).get(arch, None)
        if app_path is None:
            raise NotImplementedError(
                "Load FW by ECAT is not implemented for this OS and architecture:"
                f" {sys_name} {arch}"
            )
        exec_path = os.path.join(os.path.dirname(inspect.getfile(bin_module)), app_path)
        logger.debug(f"Call FoE application for {sys_name}-{arch}")
        try:
            subprocess.run(
                [exec_path, self.interface_name, f"{slave_id}", fw_file],
                check=True,
                shell=True,
                encoding="utf-8",
            )
        except subprocess.CalledProcessError as e:
            foe_return_error = self.FOE_ERRORS.get(e.returncode, self.UNKNOWN_FOE_ERROR)
            raise ILFirmwareLoadError(
                f"The firmware file could not be loaded correctly. {foe_return_error}"
            ) from e
        logger.info("Firmware updated successfully")

    @property
    def protocol(self):
        """NET_PROT: Obtain network protocol."""
        return NET_PROT.ECAT

    def _get_servo_state(self, slave_id: int) -> NET_STATE:
        return self.__servos_state[slave_id]

    def _set_servo_state(self, slave_id: int, state: NET_STATE) -> None:
        self.__servos_state[slave_id] = state

    def _notify_status(self, slave_id: int, status: NET_DEV_EVT) -> None:
        """Notify subscribers of a network state change."""
        for callback in self.__observers_net_state[slave_id]:
            callback(status)
