import os
import sys
import platform
import subprocess
import inspect
import time
from collections import defaultdict
from typing import Optional, Any, Callable, List, Dict, TYPE_CHECKING, Union
from threading import Thread

import ingenialogger

try:
    import pysoem
except ImportError as ex:
    pysoem = None
    pysoem_import_error = ex

if TYPE_CHECKING:
    from pysoem import CdefSlave

from ingenialink.network import Network, NET_PROT, NET_STATE, NET_DEV_EVT
from ingenialink.exceptions import ILFirmwareLoadError, ILError, ILStateError
from ingenialink import bin as bin_module
from ingenialink.ethercat.servo import EthercatServo

logger = ingenialogger.get_logger(__name__)


class NetStatusListener(Thread):
    """Network status listener thread to check if the drive is alive.

    Args:
        network: Network instance of the EtherCAT communication.

    """

    def __init__(self, network: "EthercatNetwork", refresh_time: float = 0.25):
        super(NetStatusListener, self).__init__()
        self.__network = network
        self.__refresh_time = refresh_time
        self.__stop = False
        self._ecat_master = self.__network._ecat_master

    def run(self) -> None:
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

    def stop(self) -> None:
        self.__stop = True


class EthercatNetwork(Network):
    """Network for all EtherCAT communications.

    Args:
        interface_name: Interface name to be targeted.
        connection_timeout: Time in seconds of the connection timeout.

    Raises:
        ImportError: WinPcap is not installed

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
    MANUAL_STATE_CHANGE = 1

    DEFAULT_ECAT_CONNECTION_TIMEOUT_S = 1
    ECAT_STATE_CHANGE_TIMEOUT_NS = 1_000_000
    ECAT_PROCESSDATA_TIMEOUT_NS = 100_000

    def __init__(
        self, interface_name: str, connection_timeout: float = DEFAULT_ECAT_CONNECTION_TIMEOUT_S
    ):
        if not pysoem:
            raise pysoem_import_error
        super(EthercatNetwork, self).__init__()
        self.interface_name: str = interface_name
        self.servos: List[EthercatServo] = []
        self.__servos_state: Dict[int, NET_STATE] = {}
        self.__listener_net_status: Optional[NetStatusListener] = None
        self.__observers_net_state: Dict[int, List[Any]] = defaultdict(list)
        self._ecat_master: pysoem.CdefMaster = pysoem.Master()
        self._ecat_master.sdo_read_timeout = int(1_000_000 * connection_timeout)
        self._ecat_master.sdo_write_timeout = int(1_000_000 * connection_timeout)
        self._ecat_master.manual_state_change = self.MANUAL_STATE_CHANGE
        self.__is_master_running = False
        self.__last_init_nodes: List[int] = []

    def scan_slaves(self) -> List[int]:
        """Scans for nodes in the network. If any node is already connected scan can not be done.

        Returns:
            List containing all the detected node IDs.

        Raises:
            ILError: If any node is already connected.

        """
        if self.servos:
            raise ILError("Some nodes are already connected")
        if not self.__is_master_running:
            self._start_master()
        self.__init_nodes()
        return self.__last_init_nodes

    def __init_nodes(self) -> None:
        """Init all the nodes and set already connected nodes to PreOp state.
        Also fill `__last_init_nodes` attribute.
        """
        self._ecat_master.slaves = []  # That is because of a bug of pysoem
        nodes = self._ecat_master.config_init()
        if self.servos:
            self._change_nodes_state(self.servos, pysoem.PREOP_STATE)
        self.__last_init_nodes = list(range(1, nodes + 1))

    def connect_to_slave(  # type: ignore [override]
        self,
        slave_id: int,
        dictionary: str,
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
            ValueError: If the slave ID is not valid.
            ILError: If no slaves are found.
            ILStateError: If slave can not reach PreOp state

        """
        if not isinstance(slave_id, int) or slave_id < 0:
            raise ValueError("Invalid slave ID value")
        if not self.__is_master_running:
            self._start_master()
        if slave_id not in self.__last_init_nodes:
            self.__init_nodes()
        if len(self.__last_init_nodes) == 0:
            raise ILError("Could not find any slaves in the network.")
        if slave_id not in self.__last_init_nodes:
            raise ILError(f"Slave {slave_id} was not found.")
        slave = self._ecat_master.slaves[slave_id - 1]
        servo = EthercatServo(slave, slave_id, dictionary, servo_status_listener)
        if not self._change_nodes_state(servo, pysoem.PREOP_STATE):
            raise ILStateError("Slave can not reach PreOp state")
        self.servos.append(servo)
        self._set_servo_state(slave_id, NET_STATE.CONNECTED)
        if net_status_listener:
            self.start_status_listener()
        return servo

    def disconnect_from_slave(self, servo: EthercatServo) -> None:  # type: ignore [override]
        """Disconnects the slave from the network.

        Args:
            servo: Instance of the servo connected.

        """
        servo.stop_status_listener()
        if not self._change_nodes_state(servo, pysoem.INIT_STATE):
            logger.warning("Drive can not reach Init state")
        self.servos.remove(servo)
        if not self.servos:
            self.stop_status_listener()
            self._ecat_master.close()
            self.__is_master_running = False
            self.__last_init_nodes = []

    def start_pdos(self) -> None:
        """Configure the PDOs and set slave state to OP for all slaves with mapped PDOs

        Raises:
            ILStateError: If slaves can not reach SafeOp state

        """
        op_servo_list = [servo for servo in self.servos if servo._rpdo_maps or servo._tpdo_maps]
        try:
            for servo in op_servo_list:
                for rpdo_map in servo._rpdo_maps:
                    rpdo_map.get_item_bytes()
        except ILError as e:
            raise ILError("RPDOs initial value should be set before start PDOs") from e
        self._ecat_master.config_map()
        self._ecat_master.state = pysoem.SAFEOP_STATE
        if not op_servo_list:
            logger.warning("No drives has PDO mapping")
            return
        if not self._change_nodes_state(op_servo_list, pysoem.SAFEOP_STATE):
            raise ILStateError("Drives can not reach SafeOp state")
        self.send_receive_processdata()
        self._change_nodes_state(op_servo_list, pysoem.OP_STATE)

    def stop_pdos(self) -> None:
        """For all slaves in OP or SafeOp state, set state to PreOp"""
        self._ecat_master.read_state()
        op_servo_list = [
            servo
            for servo in self.servos
            if servo.slave.state in [pysoem.OP_STATE, pysoem.SAFEOP_STATE]
        ]
        if not self._change_nodes_state(op_servo_list, pysoem.PREOP_STATE):
            logger.warning("Drive can not reach PreOp state")

    def send_receive_processdata(self) -> None:
        for servo in self.servos:
            servo.process_pdo_inputs()
        self._ecat_master.send_processdata()
        processdata_wkc = self._ecat_master.receive_processdata(
            timeout=self.ECAT_PROCESSDATA_TIMEOUT_NS
        )
        for servo in self.servos:
            servo.generate_pdo_outputs()

    def _change_nodes_state(
        self, nodes: Union["EthercatServo", List["EthercatServo"]], target_state: int
    ) -> bool:
        """Set ECAT state to target state for all nodes in list

        Args:
            nodes: target node or list of nodes
            target_state: target ECAT state

        Returns:
            True if all nodes reached the target state, else False.
        """
        node_list = nodes if isinstance(nodes, list) else [nodes]
        for drive in node_list:
            drive.slave.state = target_state
            drive.slave.write_state()
        self._ecat_master.read_state()

        return all(
            target_state
            == drive.slave.state_check(target_state, self.ECAT_STATE_CHANGE_TIMEOUT_NS)
            for drive in node_list
        )

    def subscribe_to_status(  # type: ignore [override]
        self, slave_id: int, callback: Callable[[str, NET_DEV_EVT], None]
    ) -> None:
        """Subscribe to network state changes.

        Args:
            slave_id: Slave ID of the drive to subscribe.
            callback: Callback function.

        """
        if callback in self.__observers_net_state[slave_id]:
            logger.info("Callback already subscribed.")
            return
        self.__observers_net_state[slave_id].append(callback)

    def unsubscribe_from_status(  # type: ignore [override]
        self, slave_id: int, callback: Callable[[str, NET_DEV_EVT], None]
    ) -> None:
        """Unsubscribe from network state changes.

        Args:
            slave_id: Slave ID of the drive to subscribe.
            callback: Callback function.

        """
        if callback not in self.__observers_net_state[slave_id]:
            logger.info("Callback not subscribed.")
            return
        self.__observers_net_state[slave_id].remove(callback)

    def start_status_listener(self) -> None:  # type: ignore [override]
        """Start monitoring network events (CONNECTION/DISCONNECTION)."""
        if self.__listener_net_status is None:
            listener = NetStatusListener(self)
            listener.start()
            self.__listener_net_status = listener

    def stop_status_listener(self) -> None:  # type: ignore [override]
        """Stops the NetStatusListener from listening to the drive."""
        if self.__listener_net_status is not None:
            self.__listener_net_status.stop()
            self.__listener_net_status.join()
        self.__listener_net_status = None

    def load_firmware(self, fw_file: str, slave_id: int = 1) -> None:  # type: ignore [override]
        """Loads a given firmware file to a target slave.

        Args:
            fw_file: Path to the firmware file.
            slave_id: Slave ID to which load the firmware file.

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

    def _start_master(self) -> None:
        """Start the EtherCAT master"""
        self._ecat_master.open(self.interface_name)
        self.__is_master_running = True

    @property
    def protocol(self) -> NET_PROT:
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
