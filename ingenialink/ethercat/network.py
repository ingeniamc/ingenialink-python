import atexit
import os
import threading
import time
from collections import OrderedDict, defaultdict
from enum import Enum
from threading import Thread
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

import ingenialogger

from ingenialink.servo import Servo
from ingenialink.utils.timeout import Timeout

try:
    import pysoem
except ImportError as ex:
    pysoem = None
    pysoem_import_error = ex

if TYPE_CHECKING:
    from pysoem import CdefSlave

from dataclasses import dataclass, field

from ingenialink.constants import ECAT_STATE_CHANGE_TIMEOUT_US
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.exceptions import (
    ILError,
    ILFirmwareLoadError,
    ILStateError,
    ILWrongWorkingCountError,
)
from ingenialink.network import NetDevEvt, NetProt, NetState, Network, SlaveInfo

logger = ingenialogger.get_logger(__name__)

# Holds a reference to the Ethercat network (used to handle no-GIL cases)
ETHERCAT_NETWORK_REFERENCES: set["EthercatNetwork"] = set()


def set_network_reference(network: "EthercatNetwork") -> None:
    """Adds a reference to an EtherCAT network.

    Args:
        network: network.
    """
    global ETHERCAT_NETWORK_REFERENCES
    ETHERCAT_NETWORK_REFERENCES.add(network)


@atexit.register  # Remove all references upon normal program termination
def release_network_reference(network: Optional["EthercatNetwork"] = None) -> None:
    """Releases a network reference.

    If `network` is not provided, all references will be removed.

    Args:
        network: network object.

    Raises:
        RuntimeError: if the specified network is not on the list.
    """
    global ETHERCAT_NETWORK_REFERENCES
    if network is None:
        ETHERCAT_NETWORK_REFERENCES.clear()
    elif network not in ETHERCAT_NETWORK_REFERENCES:
        raise RuntimeError("Could not release reference of network.")
    else:
        ETHERCAT_NETWORK_REFERENCES.remove(network)


@dataclass(frozen=True)
class GilReleaseConfig:
    """Configuration of pysoem functions that have GIL release control."""

    config_init: Optional[bool] = None
    sdo_read_write: Optional[bool] = None
    foe_read_write: Optional[bool] = None
    send_receive_processdata: Optional[bool] = None
    _always_release: bool = field(init=False, default=False)

    @property
    def always_release(self) -> bool:
        """Returns True if the GIL should be released for all functions, False otherwise."""
        return self._always_release

    @classmethod
    def always(cls) -> "GilReleaseConfig":
        """Releases the GIL from all functions.

        Returns:
            GIL configuration.
        """
        instance = cls(
            config_init=True,
            sdo_read_write=True,
            foe_read_write=True,
            send_receive_processdata=True,
        )
        object.__setattr__(instance, "_always_release", True)  # frozen instance
        return instance


class SlaveState(Enum):
    """EtherCAT state enum."""

    NONE_STATE = 0
    INIT_STATE = 1
    PREOP_STATE = 2
    BOOT_STATE = 3
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
        super().__init__()
        self.__network = network
        self.__refresh_time = refresh_time
        self.__stop = False
        self._ecat_master = self.__network._ecat_master

    def run(self) -> None:
        """Check the network status."""
        while not self.__stop:
            self._ecat_master.read_state()
            for servo in self.__network.servos:
                slave_id = servo.slave_id
                servo_state = self.__network.get_servo_state(slave_id)
                is_servo_alive = servo.slave.state != pysoem.NONE_STATE
                if not is_servo_alive and servo_state == NetState.CONNECTED:
                    self.__network._notify_status(slave_id, NetDevEvt.REMOVED)
                    self.__network._set_servo_state(slave_id, NetState.DISCONNECTED)
                if (
                    is_servo_alive
                    and servo_state == NetState.DISCONNECTED
                    and self.__network._recover_from_disconnection()
                ):
                    self.__network._notify_status(slave_id, NetDevEvt.ADDED)
                    self.__network._set_servo_state(slave_id, NetState.CONNECTED)
                time.sleep(self.__refresh_time)

    def stop(self) -> None:
        """Check the network status."""
        self.__stop = True


class EthercatNetwork(Network):
    """Network for all EtherCAT communications.

    Args:
        interface_name: Interface name to be targeted.
        connection_timeout: Time in seconds of the connection timeout.
        overlapping_io_map: Map PDOs to overlapping IO map.
        gil_release_config: configures which functions should release the GIL.

    Raises:
        ImportError: WinPcap is not installed

    """

    MANUAL_STATE_CHANGE = 1

    DEFAULT_ECAT_CONNECTION_TIMEOUT_S = 1
    ECAT_PROCESSDATA_TIMEOUT_S = 0.1

    EXPECTED_WKC_PROCESS_DATA = 3

    DEFAULT_FOE_PASSWORD = 0x70636675
    __FOE_WRITE_TIMEOUT_US = 500_000
    __FOE_RECOVERY_TIMEOUT_S = 90
    __FOE_RECOVERY_SLEEP_S = 5

    __FORCE_BOOT_PASSWORD = 0x424F4F54
    __FORCE_COCO_BOOT_IDX = 0x5EDE
    __FORCE_COCO_BOOT_SUBIDX = 0x00
    __FORCE_BOOT_SLEEP_TIME_S = 5

    __DEFAULT_FOE_FILE_NAME = "firmware_file"

    __MAX_FOE_TRIES = 2

    def __init__(
        self,
        interface_name: str,
        connection_timeout: float = DEFAULT_ECAT_CONNECTION_TIMEOUT_S,
        overlapping_io_map: bool = True,
        gil_release_config: GilReleaseConfig = GilReleaseConfig(),
    ):
        if not pysoem:
            raise pysoem_import_error
        super().__init__()
        self.interface_name: str = interface_name
        self.servos: list[EthercatServo] = []
        self.__listener_net_status: Optional[NetStatusListener] = None
        self.__observers_net_state: dict[int, list[Any]] = defaultdict(list)
        self._ecat_master: pysoem.CdefMaster = pysoem.Master()
        self.__gil_release_config = gil_release_config
        self._ecat_master.always_release_gil = self.__gil_release_config.always_release
        timeout_us = int(1_000_000 * connection_timeout)
        self.update_sdo_timeout(timeout_us, timeout_us)
        self._ecat_master.manual_state_change = self.MANUAL_STATE_CHANGE
        self._overlapping_io_map = overlapping_io_map
        self.__is_master_running = False
        self.__last_init_nodes: list[int] = []

        self._lock = threading.Lock()
        set_network_reference(network=self)

    def update_sdo_timeout(self, sdo_read_timeout: int, sdo_write_timeout: int) -> None:
        """Update SDO timeouts for all the drives.

        Args:
            sdo_read_timeout: timeout for SDO read access in us
            sdo_write_timeout: timeout for SDO write access in us

        """
        self._ecat_master.sdo_read_timeout = sdo_read_timeout
        self._ecat_master.sdo_write_timeout = sdo_write_timeout

    @staticmethod
    def update_pysoem_timeouts(
        ret: int, safe: int, eeprom: int, tx_mailbox: int, rx_mailbox: int, state: int
    ) -> None:
        """Update pysoem timeouts.

        Args:
            ret: new ret timeout.
            safe: new safe timeout.
            eeprom: new EEPROM access timeout.
            tx_mailbox: new Tx mailbox cycle timeout.
            rx_mailbox: new Rx mailbox cycle timeout.
            state: new status check timeout.
        """
        if not pysoem:
            raise pysoem_import_error
        pysoem.settings.timeouts.ret = ret
        pysoem.settings.timeouts.safe = safe
        pysoem.settings.timeouts.eeprom = eeprom
        pysoem.settings.timeouts.tx_mailbox = tx_mailbox
        pysoem.settings.timeouts.rx_mailbox = rx_mailbox
        pysoem.settings.timeouts.state = state

    @staticmethod
    def __get_foe_error_message(error_code: int) -> str:
        """Error message associated with an error code.

        Args:
            error_code: FoE error code.

        Returns:
            Error message.
        """
        # Error codes taken from SOEM source code.
        # https://github.com/OpenEtherCATsociety/SOEM/blob/v1.4.0/soem/ethercatfoe.c#L199
        if error_code == -3:
            return "Unexpected mailbox received"
        if error_code == -5:
            return "FoE error"
        if error_code == -6:
            return "Buffer too small"
        if error_code == -7:
            return "Packet number error"
        if error_code == -10:
            return "File not found"
        return f" Error code: {error_code}."

    def scan_slaves(self) -> list[int]:
        """Scans for slaves in the network.

        Scanning of slaves cannot be done if a slave is already
        connected to the network.

        Returns:
            List containing all the detected slaves.

        Raises:
            ILError: If any slaves is already connected.

        """
        if self.servos:
            raise ILError("Some slaves are already connected")
        is_master_running_before_scan = self.__is_master_running
        if not is_master_running_before_scan:
            self._start_master()
        self.__init_nodes()
        slaves_found = self.__last_init_nodes
        if not is_master_running_before_scan:
            self.close_ecat_master(release_reference=False)
        return slaves_found

    def scan_slaves_info(self) -> OrderedDict[int, SlaveInfo]:
        """Scans for slaves in the network and return an ordered dict with the slave information.

        Returns:
            Ordered dict with the slave information.
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

    def __init_nodes(self, *, release_gil: Optional[bool] = None) -> None:
        """Init all the nodes and set already connected nodes to PreOp state.

        Also fill `__last_init_nodes` attribute.

        Args:
            release_gil: used to overwrite the GIL release configuration.
                True to release the GIL, False otherwise.
                If not specified, default GIL release configuration will be used.
        """
        if release_gil is None:
            release_gil = self.__gil_release_config.config_init
        self._lock.acquire()
        nodes = self._ecat_master.config_init(release_gil=release_gil)
        self._lock.release()
        if len(self.servos):
            self._change_nodes_state(self.servos, pysoem.PREOP_STATE)
        if nodes is not None:
            self.__last_init_nodes = list(range(1, nodes + 1))

    def connect_to_slave(
        self,
        slave_id: int,
        dictionary: str,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ) -> EthercatServo:
        """Connects to a drive through a given slave number.

        Args:
            slave_id: Targeted slave to be connected.
            dictionary: Path to the dictionary file.
            servo_status_listener: Toggle the listener of the servo for
                its status, errors, faults, etc.
            net_status_listener: Toggle the listener of the network
                status, connection and disconnection.
            disconnect_callback: Callback function to be called when the servo is disconnected.
                If not specified, no callback will be called.

        Raises:
            ValueError: If the slave ID is not valid.
            ILError: If no slaves are found.
            ILStateError: If slave can not reach PreOp state

        Returns:
            ethercat servo.
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
            slave,
            slave_id,
            dictionary,
            servo_status_listener,
            sdo_read_write_release_gil=self.__gil_release_config.sdo_read_write,
            disconnect_callback=disconnect_callback,
        )
        if not self._change_nodes_state(servo, pysoem.PREOP_STATE):
            if servo_status_listener:
                servo.stop_status_listener()
            raise ILStateError("Slave can not reach PreOp state")
        servo.reset_pdo_mapping()
        self.servos.append(servo)
        self._set_servo_state(slave_id, NetState.CONNECTED)
        if net_status_listener:
            self.start_status_listener()
        return servo

    def close_ecat_master(self, release_reference: bool = True) -> None:
        """Closes the connection with the EtherCAT master.

        Args:
            release_reference: Whether to release the network reference.
        If the network will be reused afterward it should be set to False.

        """
        self._lock.acquire()
        self._ecat_master.close()
        self._lock.release()
        self.__is_master_running = False
        self.__last_init_nodes = []
        if release_reference:
            release_network_reference(network=self)

    def disconnect_from_slave(self, servo: EthercatServo) -> None:  # type: ignore [override]
        """Disconnects the slave from the network.

        Args:
            servo: Instance of the servo connected.

        """
        # Notify that disconnect_from_slave has been called
        if servo._disconnect_callback:
            servo._disconnect_callback(servo)
        if not self._change_nodes_state(servo, pysoem.INIT_STATE):
            logger.warning("Drive can not reach Init state")
        servo.teardown()
        self.servos.remove(servo)
        if not self.servos:
            self.stop_status_listener()
            self.close_ecat_master()

    def config_pdo_maps(self) -> None:
        """Configure the PDO maps.

        It maps the PDO maps of each slave and sets its state to SafeOP.

        """
        if self._overlapping_io_map:
            self._ecat_master.config_overlap_map()
        else:
            self._ecat_master.config_map()

    def start_pdos(self, timeout: float = 2.0) -> None:
        """Set all slaves with mapped PDOs to Operational State.

        Args:
            timeout: timeout in seconds to reach Op state, 2.0 seconds by default.

        Raises:
            ILError: If the RPDO values are not set before starting the PDO exchange process.
            ILStateError: If slaves can not reach SafeOp or Op state.
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
        # Configure the PDO maps
        self.config_pdo_maps()

        with Timeout(timeout) as t:
            # Set all slaves to SafeOp state
            self._ecat_master.state = pysoem.SAFEOP_STATE
            self._change_nodes_state(op_servo_list, pysoem.SAFEOP_STATE)
            while not self._check_node_state(op_servo_list, pysoem.SAFEOP_STATE):
                if t.has_expired:
                    raise ILStateError("Drives can not reach SafeOp state")

            # Set all slaves to Op state
            self._change_nodes_state(op_servo_list, pysoem.OP_STATE)
            while not self._check_node_state(op_servo_list, pysoem.OP_STATE):
                self.send_receive_processdata()
                if t.has_expired:
                    raise ILStateError("Drives can not reach Op state")

    def stop_pdos(self) -> None:
        """For all slaves in OP or SafeOp state, set state to PreOp."""
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

    def send_receive_processdata(
        self, timeout: float = ECAT_PROCESSDATA_TIMEOUT_S, *, release_gil: Optional[bool] = None
    ) -> None:
        """Send and receive PDOs.

        Args:
            timeout: receive processdata timeout in seconds, 0.1 seconds by default.
            release_gil: used to overwrite the GIL release configuration.
                True to release the GIL, False otherwise.
                If not specified, default GIL release configuration will be used.

        Raises:
            ILWrongWorkingCountError: If processdata working count is wrong

        """
        if release_gil is None:
            release_gil = self.__gil_release_config.send_receive_processdata
        for servo in self.servos:
            servo.generate_pdo_outputs()
        self._lock.acquire()
        if self._overlapping_io_map:
            self._ecat_master.send_overlap_processdata()
        else:
            self._ecat_master.send_processdata(release_gil=release_gil)
        processdata_wkc = self._ecat_master.receive_processdata(
            timeout=int(timeout * 1_000_000), release_gil=release_gil
        )
        self._lock.release()
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
            raise ILWrongWorkingCountError(
                f"Processdata working count is wrong, expected: {self._ecat_master.expected_wkc},"
                f" real: {processdata_wkc}. {servos_state_msg}"
            )
        for servo in self.servos:
            servo.process_pdo_inputs()

    def _change_nodes_state(
        self, nodes: Union["EthercatServo", list["EthercatServo"]], target_state: int
    ) -> bool:
        """Set ECAT state to target state for all nodes in list.

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
        self, nodes: Union["EthercatServo", list["EthercatServo"]], target_state: int
    ) -> bool:
        """Check ECAT state for all nodes in list.

        Args:
            nodes: target node or list of nodes
            target_state: target ECAT state

        Returns:
            True if all nodes reached the target state, else False.
        """
        if not nodes:
            return False

        node_list = nodes if isinstance(nodes, list) else [nodes]
        self._ecat_master.read_state()

        return all(
            target_state == drive.slave.state_check(target_state, ECAT_STATE_CHANGE_TIMEOUT_US)
            for drive in node_list
        )

    def subscribe_to_status(  # type: ignore [override]
        self, slave_id: int, callback: Callable[[NetDevEvt], None]
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
        self, slave_id: int, callback: Callable[[str, NetDevEvt], None]
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
            AttributeError: If the boot_in_app argument is not a boolean.
            FileNotFoundError: If the firmware file cannot be found.
            ValueError: If the salve ID value is invalid.
            ILError: If no slaves could be found in the network.
            ILError: If the slave ID couldn't be found in the network.
            ILFirmwareLoadError: If the FoE write operation is not successful.
        """
        if not isinstance(boot_in_app, bool):
            raise AttributeError("The boot_in_app argument should be a boolean.")

        if not os.path.isfile(fw_file):
            raise FileNotFoundError(f"Could not find {fw_file}.")

        if password is None:
            password = self.DEFAULT_FOE_PASSWORD

        if not isinstance(slave_id, int) or slave_id < 0:
            raise ValueError("Invalid slave ID value")
        is_master_running_before_loading_firmware = self.__is_master_running
        if not is_master_running_before_loading_firmware:
            self._start_master()
            self.__init_nodes()
        if len(self.__last_init_nodes) == 0:
            raise ILError("Could not find any slaves in the network.")
        if slave_id not in self.__last_init_nodes:
            raise ILError(f"Slave {slave_id} was not found.")

        slave = self._ecat_master.slaves[slave_id - 1]
        error_messages: list[str] = []
        for iteration in range(self.__MAX_FOE_TRIES):
            if not boot_in_app:
                self._force_boot_mode(slave)
            if not self._switch_to_boot_state(slave):
                error_message = f"Attempt {iteration + 1}: The slave cannot reach the Boot state."
                logger.info(error_message)
                error_messages.append(error_message)
                continue
            foe_write_result = self._write_foe(slave, fw_file, password)
            if foe_write_result > 0:
                break
            error_message = (
                f"Attempt {iteration + 1}: "
                f"{self.__get_foe_error_message(error_code=foe_write_result)}."
            )
            logger.info(f"FoE write failed: {error_message}")
            error_messages.append(error_message)
            self.__init_nodes()
        else:
            combined_errors = "\n".join(error_messages)
            raise ILFirmwareLoadError(
                f"The firmware file could not be loaded correctly after {self.__MAX_FOE_TRIES}"
                f" attempts. Errors:\n{combined_errors}"
            )
        start_time = time.time()
        recovered = False
        while time.time() < (start_time + self.__FOE_RECOVERY_TIMEOUT_S) and not recovered:
            self.__init_nodes()
            slave.state = pysoem.PREOP_STATE
            slave.write_state()
            recovered = (
                slave.state_check(pysoem.PREOP_STATE, ECAT_STATE_CHANGE_TIMEOUT_US)
                == pysoem.PREOP_STATE
            )
            time.sleep(self.__FOE_RECOVERY_SLEEP_S)
        if recovered:
            logger.info("Firmware updated successfully")
        else:
            logger.info(f"The slave {slave_id} cannot reach the PreOp state.")
        if not is_master_running_before_loading_firmware:
            self.close_ecat_master(release_reference=False)

    def _switch_to_boot_state(self, slave: "CdefSlave") -> bool:
        """Transitions the slave to the boot state.

        Returns:
            True if the slave reached the boot state, False otherwise.
        """
        slave.state = pysoem.BOOT_STATE
        slave.write_state()
        return bool(
            slave.state_check(pysoem.BOOT_STATE, ECAT_STATE_CHANGE_TIMEOUT_US) == pysoem.BOOT_STATE
        )

    def _force_boot_mode(self, slave: "CdefSlave") -> None:
        """COMOCO drives need to be forced to boot mode.

        Raises:
            ILFirmwareLoadError: If there is an error writing to the Boot mode register.
        """
        slave.state = pysoem.PREOP_STATE
        slave.write_state()
        if (
            slave.state_check(pysoem.PREOP_STATE, ECAT_STATE_CHANGE_TIMEOUT_US)
            == pysoem.PREOP_STATE
        ):
            try:
                slave.sdo_write(
                    self.__FORCE_COCO_BOOT_IDX,
                    self.__FORCE_COCO_BOOT_SUBIDX,
                    self.__FORCE_BOOT_PASSWORD.to_bytes(4, "little"),
                )
            except pysoem.WkcError as e:
                raise ILFirmwareLoadError("Error writing to the Boot mode register.") from e
        slave.state = pysoem.INIT_STATE
        slave.write_state()
        slave.state = pysoem.BOOT_STATE
        slave.write_state()
        time.sleep(self.__FORCE_BOOT_SLEEP_TIME_S)
        self.__init_nodes()

    def _write_foe(
        self,
        slave: "CdefSlave",
        file_path: str,
        password: int,
        *,
        release_gil: Optional[bool] = None,
    ) -> int:
        """Write the firmware file via FoE.

        Args:
            slave: The pysoem slave object.
            file_path: The firmware file path.
            password: The firmware password.
            release_gil: used to overwrite the GIL release configuration.
                True to release the GIL, False otherwise.
                If not specified, default GIL release configuration will be used.

        Returns:
            The FOE operation result.

        """
        if release_gil is None:
            release_gil = self.__gil_release_config.foe_read_write
        with open(file_path, "rb") as file:
            file_data = file.read()
            self._lock.acquire()
            r: int = slave.foe_write(
                self.__DEFAULT_FOE_FILE_NAME,
                password,
                file_data,
                self.__FOE_WRITE_TIMEOUT_US,
                release_gil=release_gil,
            )
            self._lock.release()
        return r

    def _start_master(self) -> None:
        """Start the EtherCAT master."""
        self._ecat_master.open(self.interface_name)
        self.__is_master_running = True

    @property
    def protocol(self) -> NetProt:
        """NetProt: Obtain network protocol."""
        return NetProt.ECAT

    def get_servo_state(self, servo_id: Union[int, str]) -> NetState:
        """Get the state of a servo that's a part of network.

        The state indicates if the servo is connected or disconnected.

        Args:
            servo_id: The servo's slave ID.

        Raises:
            ValueError: If the servo ID is not an integer.

        Returns:
            The servo's state.
        """
        if not isinstance(servo_id, int):
            raise ValueError("The servo ID must be an int.")
        return self._servos_state[servo_id]

    def _set_servo_state(self, servo_id: Union[int, str], state: NetState) -> None:
        """Set the state of a servo that's a part of network.

        Args:
            servo_id: The servo's slave ID.
            state: The servo's state.

        """
        self._servos_state[servo_id] = state

    def _notify_status(self, slave_id: int, status: NetDevEvt) -> None:
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
        if not self.servos:
            log_message = (
                "The CoE communication cannot be recovered. No slaves where detected in the network"
            )
            return False
        all_drives_in_preop = self._check_node_state(self.servos, pysoem.PREOP_STATE)
        if all_drives_in_preop:
            log_message = "CoE communication recovered."
        else:
            log_message = (
                "The CoE communication cannot be recovered. Not all slaves reached the PreOp state"
            )
        logger.warning(log_message)
        return all_drives_in_preop
