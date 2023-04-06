import os
import sys
import platform
import subprocess

try:
    import importlib.resources as pkg_resources
except ImportError:
    import importlib_resources as pkg_resources

import ingenialogger

from ingenialink.network import NET_PROT
from ingenialink.exceptions import ILFirmwareLoadError
from ingenialink import bin as bin_module

logger = ingenialogger.get_logger(__name__)


class EthercatNetwork:
    """Network for all EtherCAT communications.

    Args:
        interface_name (str): Interface name to be targeted.

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

    def __init__(self, interface_name):
        self.interface_name = interface_name
        """str: Interface name used in the network settings."""
        self.servos = []
        """list: List of the connected servos in the network."""
        self._ecat_master = None

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
        exec_path = os.path.join(str(pkg_resources.files(bin_module)), app_path)
        logger.debug(f"Call FoE application for {sys_name}-{arch}")
        try:
            subprocess.run([exec_path, self.interface_name, f"{slave_id}", fw_file], check=True)
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
