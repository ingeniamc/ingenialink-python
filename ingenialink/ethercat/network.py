import os
import sys
import platform
import subprocess
import inspect
from typing import Optional

import ingenialogger
import pysoem

from ingenialink.network import Network, NET_PROT
from ingenialink.exceptions import ILFirmwareLoadError, ILError
from ingenialink import bin as bin_module
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.constants import DEFAULT_ECAT_CONNECTION_TIMEOUT

logger = ingenialogger.get_logger(__name__)


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
        self.interface_name = interface_name
        """str: Interface name used in the network settings."""
        self.servos = []
        """list: List of the connected servos in the network."""
        self._ecat_master = pysoem.Master()
        self._ecat_master.open(self.interface_name)
        self._ecat_master.sdo_read_timeout = int(1_000_000 * connection_timeout)
        self._ecat_master.sdo_write_timeout = int(1_000_000 * connection_timeout)

    def scan_slaves(self) -> list[int]:
        """Scans for nodes in the network.

        Returns:
            Lis containing all the detected node IDs.

        """
        nodes = self._ecat_master.config_init()
        return list(range(1, nodes + 1))

    def connect_to_slave(
        self,
        slave_id: int,
        dictionary: Optional[str] = None,
        servo_status_listener: bool = False,
        net_status_listener: bool = False,
    ):
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
        servo = EthercatServo(slave, dictionary, servo_status_listener)
        self.servos.append(servo)
        if net_status_listener:
            self.start_status_listener(servo)
        return servo

    def disconnect_from_slave(self, servo):
        raise NotImplementedError

    def subscribe_to_status(self, callback):
        raise NotImplementedError

    def unsubscribe_from_status(self, callback):
        raise NotImplementedError

    def start_status_listener(self, *args, **kwargs):
        raise NotImplementedError

    def stop_status_listener(self, *args, **kwargs):
        raise NotImplementedError

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
