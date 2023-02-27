import os
import time

from pysoem import Master, INIT_STATE, BOOT_STATE
import ingenialogger

from ingenialink.network import NET_PROT
from ingenialink.constants import (
    FILE_EXT_SFU,
    FILE_EXT_LFU,
    FORCE_BOOT_PASSWORD,
    FORCE_COCO_BOOT_IDX,
    FORCE_COCO_BOOT_SUBIDX,
    FOE_WRITE_PASSWORD,
    FOE_WRITE_TIMEOUT,
)
from ingenialink.enums.ethercat import EC_STATE
from ingenialink.exceptions import ILFirmwareLoadError

logger = ingenialogger.get_logger(__name__)


class EthercatNetwork:
    """Network for all EtherCAT communications.

    Args:
        interface_name (str): Interface name to be targeted.

    """
    STATE_CHECK_TIMEOUT = 50_000

    def __init__(self, interface_name):
        self.interface_name = interface_name
        """str: Interface name used in the network settings."""
        self.servos = []
        """list: List of the connected servos in the network."""
        self._ecat_master = None

    def load_firmware(self, fw_file, slave_id=1, boot_in_app=None):
        """Loads a given firmware file to a target slave.

        .. warning ::
            It is needed to disconnect the drive(:func:`disconnect_from_slave`)
            after loading the firmware since the `Servo` object's data will
            become obsolete.

        Args:
            fw_file (str): Path to the firmware file.
            slave_id (int): Slave ID to which load the firmware file.
            boot_in_app (bool): If ``fw_file`` extension is .sfu -> True.
                                Otherwise -> False.

        Raises:
            FileNotFoundError: If the firmware file cannot be found.
            ValueError: If the firmware file has the wrong extension.
            ILFirmwareLoadError: If no slave is detected.
            ILFirmwareLoadError: If the FOE write operation is not
            successful.

        """
        if not os.path.isfile(fw_file):
            raise FileNotFoundError(f"Could not find {fw_file}.")
        if boot_in_app is None:
            if not fw_file.endswith((FILE_EXT_SFU, FILE_EXT_LFU)):
                raise ValueError(
                    f"Firmware file should have extension {FILE_EXT_SFU} or {FILE_EXT_LFU}."
                )
            boot_in_app = fw_file.endswith(FILE_EXT_SFU)
        self._init_ecat_master()
        slave = self._ecat_master.slaves[slave_id - 1]
        if not boot_in_app:
            slave.sdo_write(
                FORCE_COCO_BOOT_IDX,
                FORCE_COCO_BOOT_SUBIDX,
                FORCE_BOOT_PASSWORD.to_bytes(4, "little"),
                False,
            )
            # COMOCO drives need to be forced two times into bootstrap state
            self._set_slave_state_to_boot()
            # Wait for drive to reset
            time.sleep(5)
            self._reset_ecat_master()
            slave = self._ecat_master.slaves[slave_id - 1]
        self._set_slave_state_to_boot()
        with open(fw_file, "rb") as file:
            file_data = file.read()
            file_name = os.path.basename(fw_file)
            r = slave.foe_write(file_name, FOE_WRITE_PASSWORD,
                                file_data, FOE_WRITE_TIMEOUT)
        self._write_slave_state(INIT_STATE)
        self._ecat_master.close()
        if r < 0:
            raise ILFirmwareLoadError(
                f"The firmware file could not be loaded correctly. Error code: {r}."
            )

    def _set_slave_state_to_boot(self):
        """Set all EtherCAT slaves to bootstrap state."""
        self._write_slave_state(INIT_STATE)
        self._write_slave_state(BOOT_STATE)

    def _write_slave_state(self, state):
        """
        Set all EtherCAT slaves to a given state.

        Args:
            state (int): State in which to set the slaves.

        """
        self._ecat_master.state = state
        self._ecat_master.write_state()
        self._check_slave_state(state)

    def _check_slave_state(self, state):
        """
        Check that slaves reaches requested state.

        Args:
            state (int): Requested state.

        """
        self._ecat_master.read_state()
        if self._ecat_master.state_check(state, timeout=self.STATE_CHECK_TIMEOUT) != state:
            logger.error(f"Slave could not reach requested state: {EC_STATE(state).name}.")

    def _init_ecat_master(self):
        """
        Initialize EtherCAT master.

        Raises:
            ILFirmwareLoadError: If no slaves are detected.

        """
        self._ecat_master = Master()
        self._ecat_master.open(self.interface_name)
        if self._ecat_master.config_init() < 0:
            raise ILFirmwareLoadError("Firmware could not be loaded. No slave detected.")

    def _close_ecat_master(self):
        """Close EtherCAT master"""
        self._ecat_master.close()

    def _reset_ecat_master(self):
        """Reset EtherCAT master"""
        self._close_ecat_master()
        self._init_ecat_master()

    @property
    def protocol(self):
        """NET_PROT: Obtain network protocol."""
        return NET_PROT.ECAT
