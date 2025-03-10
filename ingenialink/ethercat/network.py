import inspect
import os
import platform
import subprocess
import sys
import time
from collections import OrderedDict, defaultdict
from enum import Enum
from threading import Thread
from typing import Any, Callable, Dict, List, Optional, Union

import ingenialogger

try:
    import pysoem
except ImportError as ex:
    pysoem = None
    pysoem_import_error = ex

from ingenialink import bin as bin_module
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.exceptions import ILError, ILFirmwareLoadError, ILStateError, ILWrongWorkingCount
from ingenialink.network import NET_DEV_EVT, NET_PROT, NET_STATE, Network, SlaveInfo

logger = ingenialogger.get_logger(__name__)


class SlaveState(Enum):
    NONE_STATE = 0
    INIT_STATE = 1
    PREOP_STATE = 2
    SAFEOP_STATE = 4
    OP_STATE = 8
    ERROR_STATE = 16
    PREOP_ERROR_STATE = PREOP_STATE + ERROR_STATE
    SAFEOP_ERROR_STATE = SAFEOP_STATE + ERROR_STATE


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
                servo_state = self.__network.get_servo_state(slave_id)
                is_servo_alive = not servo.slave.state == pysoem.NONE_STATE
                if not is_servo_alive and servo_state == NET_STATE.CONNECTED:
                    self.__network._notify_status(slave_id, NET_DEV_EVT.REMOVED)
                    self.__network._set_servo_state(slave_id, NET_STATE.DISCONNECTED)
                if (
                    is_servo_alive
                    and servo_state == NET_STATE.DISCONNECTED
                    and self.__network._recover_from_disconnection()
                ):
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
        overlapping_io_map: Map PDOs to overlapping IO map.

    Raises:
        ImportError: WinPcap is not installed

    """

    FOE_APPLICATION = {
        "win32": {"64bit": "FoE/win_64x/FoEUpdateFirmware.exe"},
        "linux": {"64bit": "FoE/linux/FoEUpdateFirmware"},
    }
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
    ECAT_STATE_CHANGE_TIMEOUT_NS = 50_000
    ECAT_PROCESSDATA_TIMEOUT_S = 0.1

    EXPECTED_WKC_PROCESS_DATA = 3

    DEFAULT_FOE_PASSWORD = 0x70636675

    def __init__(
        self,
        interface_name: str,
        connection_timeout: float = DEFAULT_ECAT_CONNECTION_TIMEOUT_S,
        overlapping_io_map: bool = True,
    ):
        if not pysoem:
            raise pysoem_import_error
        super(EthercatNetwork, self).__init__()
        self.interface_name: str = interface_name
        self.servos: List[EthercatServo] = []
        self.__listener_net_status: Optional[NetStatusListener] = None
        self.__observers_net_state: Dict[int, List[Any]] = defaultdict(list)
        self._connection_timeout: float = connection_timeout
        self._ecat_master: pysoem.CdefMaster = pysoem.Master()
        self._ecat_master.sdo_read_timeout = int(1_000_000 * self._connection_timeout)
        self._ecat_master.sdo_write_timeout = int(1_000_000 * self._connection_timeout)
        self._ecat_master.manual_state_change = self.MANUAL_STATE_CHANGE
        self._overlapping_io_map = overlapping_io_map
        self.__is_master_running = False
        self.__last_init_nodes: List[int] = []

    def scan_slaves(self) -> List[int]:
        """Scans for slaves in the network. Scanning of slaves cannot be done if a slave is already
        connected to the network.

        Returns:
            List containing all the detected slaves.

        Raises:
            ILError: If any slaves is already connected.

        """
        if self.servos:
            raise ILError("Some slaves are already connected")
        if not self.__is_master_running:
            self._start_master()
        self.__init_nodes()
        return self.__last_init_nodes

    def scan_slaves_info(self) -> OrderedDict[int, SlaveInfo]:
        """Scans for slaves in the network and return an ordered dict with the slave information.

        Returns:
            Ordered dict with the slave information.

        Raises:
            ILError: If any slave is already connected.

        """
        slave_info: OrderedDict[int, SlaveInfo] = OrderedDict()
        try:
            slaves = self.scan_slaves()
        except ILError:
            return slave_info
        for slave_id in slaves:
            slave = self._ecat_master.slaves[slave_id - 1]
            slave_info[slave_id] = SlaveInfo(slave.id, slave.rev)
        return slave_info

    def __init_nodes(self) -> None:
        """Init all the nodes and set already connected nodes to PreOp state.
        Also fill `__last_init_nodes` attribute.
        """
        nodes = self._ecat_master.config_init()
        if self.servos:
            self._change_nodes_state(self.servos, pysoem.PREOP_STATE)
        self.__last_init_nodes = list(range(1, nodes + 1))

    def connect_to_slave(
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
        servo = EthercatServo(
            slave, slave_id, dictionary, self._connection_timeout, servo_status_listener
        )
        if not self._change_nodes_state(servo, pysoem.PREOP_STATE):
            if servo_status_listener:
                servo.stop_status_listener()
            raise ILStateError("Slave can not reach PreOp state")
        servo.reset_pdo_mapping()
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

    def config_pdo_maps(self) -> None:
        """Configure the PDO maps.

        It maps the PDO maps of each slave and sets its state to SafeOP.

        """
        if self._overlapping_io_map:
            self._ecat_master.config_overlap_map()
        else:
            self._ecat_master.config_map()

    def start_pdos(self, timeout: float = 1.0) -> None:
        """Set all slaves with mapped PDOs to Operational State.

        Args:
            timeout: timeout in seconds to reach Op state, 1.0 seconds by default.

        Raises:
            ILStateError: If slaves can not reach SafeOp or Op state

        """
        op_servo_list = [servo for servo in self.servos if servo._rpdo_maps or servo._tpdo_maps]
        if not op_servo_list:
            logger.warning("There are no PDOs assigned to any connected slave.")
            return
        try:
            for servo in op_servo_list:
                for rpdo_map in servo._rpdo_maps:
                    rpdo_map.get_item_bytes()
        except ILError as e:
            raise ILError(
                "The RPDO values should be set before starting the PDO exchange process."
            ) from e
        self.config_pdo_maps()
        self._ecat_master.state = pysoem.SAFEOP_STATE
        if not self._change_nodes_state(op_servo_list, pysoem.SAFEOP_STATE):
            raise ILStateError("Drives can not reach SafeOp state")
        self._change_nodes_state(op_servo_list, pysoem.OP_STATE)
        init_time = time.time()
        while not self._check_node_state(op_servo_list, pysoem.OP_STATE):
            self.send_receive_processdata()
            if timeout < time.time() - init_time:
                raise ILStateError("Drives can not reach Op state")

    def stop_pdos(self) -> None:
        """For all slaves in OP or SafeOp state, set state to PreOp"""
        self._ecat_master.read_state()
        op_servo_list = [
            servo
            for servo in self.servos
            if servo.slave.state in [pysoem.OP_STATE, pysoem.SAFEOP_STATE]
        ]
        if len(op_servo_list) == 0:
            return
        if not self._change_nodes_state(op_servo_list, pysoem.INIT_STATE):
            logger.warning("Not all drives could reach the Init state")
        self.__init_nodes()

    def send_receive_processdata(self, timeout: float = ECAT_PROCESSDATA_TIMEOUT_S) -> None:
        """Send and receive PDOs

        Args:
            timeout: receive processdata timeout in seconds, 0.1 seconds by default.

        Raises:
            ILWrongWorkingCount: If processdata working count is wrong

        """
        for servo in self.servos:
            servo.generate_pdo_outputs()
        if self._overlapping_io_map:
            self._ecat_master.send_overlap_processdata()
        else:
            self._ecat_master.send_processdata()
        processdata_wkc = self._ecat_master.receive_processdata(timeout=int(timeout * 1_000_000))
        if processdata_wkc != self.EXPECTED_WKC_PROCESS_DATA * (len(self.servos)):
            self._ecat_master.read_state()
            servos_state_msg = ""
            for servo in self.servos:
                servos_state_msg += (
                    f"Slave {servo.slave_id}: state {SlaveState(servo.slave.state).name}"
                )
                if servo.slave.al_status != 0:
                    al_status = pysoem.al_status_code_to_string(servo.slave.al_status)
                    servos_state_msg += f", AL status {al_status}."
                else:
                    servos_state_msg += ". "
            raise ILWrongWorkingCount(
                f"Processdata working count is wrong, expected: {self._ecat_master.expected_wkc},"
                f" real: {processdata_wkc}. {servos_state_msg}"
            )
        for servo in self.servos:
            servo.process_pdo_inputs()

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
        return self._check_node_state(nodes, target_state)

    def _check_node_state(
        self, nodes: Union["EthercatServo", List["EthercatServo"]], target_state: int
    ) -> bool:
        """Check ECAT state for all nodes in list

        Args:
            nodes: target node or list of nodes
            target_state: target ECAT state

        Returns:
            True if all nodes reached the target state, else False.
        """
        node_list = nodes if isinstance(nodes, list) else [nodes]
        self._ecat_master.read_state()

        return all(
            target_state == drive.slave.state_check(target_state, self.ECAT_STATE_CHANGE_TIMEOUT_NS)
            for drive in node_list
        )

    def subscribe_to_status(  # type: ignore [override]
        self, slave_id: int, callback: Callable[[NET_DEV_EVT], None]
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

    def load_firmware(
        self, fw_file: str, boot_in_app: bool, slave_id: int = 1, password: Optional[int] = None
    ) -> None:
        """Loads a given firmware file to a target slave.

        Args:
            fw_file: Path to the firmware file.
            boot_in_app: True if the application includes the bootloader (i.e, ``fw_file`` extension
                is .sfu), False otherwise.
            slave_id: Slave ID to which load the firmware file.
            password: Password to load the firmware file. If ``None`` the default password will be
                used.

        Raises:
            FileNotFoundError: If the firmware file cannot be found.
            ILFirmwareLoadError: If no slave is detected.
            ILFirmwareLoadError: If the FoE write operation is not successful.
            NotImplementedError: If FoE is not implemented for the current OS and architecture
            AttributeError: If the boot_in_app argument is not a boolean.
        """
        if not isinstance(boot_in_app, bool):
            raise AttributeError("The boot_in_app argument should be a boolean.")

        if not os.path.isfile(fw_file):
            raise FileNotFoundError(f"Could not find {fw_file}.")

        if password is None:
            password = self.DEFAULT_FOE_PASSWORD

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
        if sys_name == "linux":
            try:
                subprocess.run(
                    f"chmod 777 {exec_path}",
                    check=True,
                    shell=True,
                    encoding="utf-8",
                )
            except subprocess.CalledProcessError as e:
                raise ILFirmwareLoadError("Could not change the FoE binary permissions.") from e
        try:
            if sys_name == "linux":
                subprocess.run(
                    f"{exec_path} {self.interface_name} {slave_id} {fw_file} "
                    f"{int(boot_in_app)} {password}",
                    check=True,
                    shell=True,
                    encoding="utf-8",
                )
            else:
                subprocess.run(
                    [
                        exec_path,
                        self.interface_name,
                        f"{slave_id}",
                        fw_file,
                        f"{int(boot_in_app)}",
                        f"{password}",
                    ],
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

    def get_servo_state(self, servo_id: Union[int, str]) -> NET_STATE:
        """Get the state of a servo that's a part of network.
        The state indicates if the servo is connected or disconnected.

        Args:
            servo_id: The servo's slave ID.

        Returns:
            The servo's state.

        """
        if not isinstance(servo_id, int):
            raise ValueError("The servo ID must be an int.")
        return self._servos_state[servo_id]

    def _set_servo_state(self, servo_id: Union[int, str], state: NET_STATE) -> None:
        """Set the state of a servo that's a part of network.

        Args:
            servo_id: The servo's slave ID.
            state: The servo's state.

        """
        self._servos_state[servo_id] = state

    def _notify_status(self, slave_id: int, status: NET_DEV_EVT) -> None:
        """Notify subscribers of a network state change."""
        for callback in self.__observers_net_state[slave_id]:
            callback(status)

    def _recover_from_disconnection(self) -> bool:
        """Recover the CoE communication after a disconnection.
        All the connected slaves need to transitioned to the PreOp state.

        Returns:
            True if all the connected slaves reach the PreOp state.

        """
        self._ecat_master.read_state()
        if self._ecat_master.state == pysoem.PREOP_STATE:
            return True
        self.__init_nodes()
        all_drives_in_preop = self._check_node_state(self.servos, pysoem.PREOP_STATE)
        if all_drives_in_preop:
            log_message = "CoE communication recovered."
        else:
            log_message = (
                "The CoE communication cannot be recovered. Not all slaves reached the PreOp state"
            )
        logger.warning(log_message)
        return all_drives_in_preop
