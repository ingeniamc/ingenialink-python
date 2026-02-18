import ingenialogger
from virtual_drive.core import VirtualDrive

logger = ingenialogger.get_logger(__name__)


class VirtualNetworkBase:
    """Base class for shared virtual network behavior."""

    def __init__(self) -> None:
        self.ip_address = VirtualDrive.IP_ADDRESS
