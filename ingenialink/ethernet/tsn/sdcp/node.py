"""Representation of an SDCP node."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Union

from ingenialink.enums.node import NodeMode
from ingenialink.ethernet.tsn.ipv6_tftp import TftpUploader
from ingenialink.ethernet.tsn.sdcp.connection import DEFAULT_SDCP_TIMEOUT_S
from ingenialink.ethernet.tsn.sdcp.servo import SDCPServo
from ingenialink.exceptions import ILStateError
from ingenialink.node import Node
from ingenialink.servo import Servo


@dataclass(frozen=True)
class SDCPNodeDiscovery:
    """Information obtained while discovering an SDCP node."""

    target: str
    interface: str
    protocol_version: int
    serial_number: int
    product_code: int
    revision_number: int
    mode: NodeMode


class SDCPNode(Node[SDCPNodeDiscovery, SDCPServo]):
    """Representation of a physical SDCP drive.

    A node preserves the identity and latest discovery information of a
    physical drive independently of its current operating mode or application
    connection.

    The product code and serial number form the stable drive identity. The
    endpoint, protocol version, revision number, and operating mode represent
    the latest discovery state and may change during the drive lifecycle.

    Args:
        discovery: Information obtained from the latest successful discovery.
    """

    def __init__(self, discovery: SDCPNodeDiscovery) -> None:
        self._discovery = discovery
        self._servo: Optional[SDCPServo] = None

    @property
    def target(self) -> str:
        """Return the current IPv6 address of the node."""
        return self._discovery.target

    @property
    def interface(self) -> str:
        """Return the network interface used to reach the node."""
        return self._discovery.interface

    @property
    def protocol_version(self) -> int:
        """Return the currently reported SDCP protocol version."""
        return self._discovery.protocol_version

    @property
    def serial_number(self) -> int:
        """Return the serial number of the physical drive."""
        return self._discovery.serial_number

    @property
    def product_code(self) -> int:
        """Return the product code of the physical drive."""
        return self._discovery.product_code

    @property
    def revision_number(self) -> int:
        """Return the currently reported firmware revision."""
        return self._discovery.revision_number

    @property
    def mode(self) -> NodeMode:
        """Return the current operating mode of the node."""
        return self._discovery.mode

    @property
    def servo(self) -> Optional[SDCPServo]:
        """Return the associated application servo, if connected."""
        return self._servo

    def update(self, discovery: SDCPNodeDiscovery) -> None:
        """Update the node with the latest discovery information.

        The product code and serial number cannot change because they identify
        the physical drive represented by this node.

        Args:
            discovery: Information obtained from the latest successful
                discovery.

        Raises:
            ValueError: If the discovery information belongs to a different
                physical drive.
            ILStateError: If the target, interface, or operating mode changes
                while the node is connected.
        """
        discovery_identity = discovery.product_code, discovery.serial_number
        if discovery_identity != self.identity:
            raise ValueError("Cannot update an SDCP node with a different drive identity")

        if self.is_connected and (
            discovery.target != self.target
            or discovery.interface != self.interface
            or discovery.mode != self.mode
        ):
            raise ILStateError(
                "Cannot update the target, interface, or mode of a connected SDCP node"
            )

        self._discovery = discovery

    def connect(
        self,
        dictionary_path: str,
        servo_status_listener: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
        connection_timeout: float = DEFAULT_SDCP_TIMEOUT_S,
    ) -> SDCPServo:
        """Connect to the application servo.

        Args:
            dictionary_path: Path to the drive dictionary.
            connection_timeout: Timeout in seconds for SDCP transactions.
            servo_status_listener: Whether to start the servo status listener.
            disconnect_callback: Callback invoked when the servo is
                disconnected.

        Returns:
            The connected SDCP servo.

        Raises:
            ILStateError: If the node is not in application mode or is already
                connected.
        """
        if self.mode != NodeMode.APPLICATION:
            raise ILStateError("Cannot connect to an SDCP node in bootloader mode")

        if self.is_connected:
            raise ILStateError("The SDCP node is already connected")

        self._servo = SDCPServo(
            target=self.target,
            interface=self.interface,
            dictionary_path=dictionary_path,
            connection_timeout=connection_timeout,
            servo_status_listener=servo_status_listener,
            disconnect_callback=disconnect_callback,
        )
        return self._servo

    def disconnect(self) -> None:
        """Disconnect the associated application servo."""
        if self._servo is None:
            return
        self._servo.disconnect()
        self._servo = None

    def load_firmware(
        self,
        firmware_file: Union[str, Path],
        callback_progress: Optional[Callable[[int], None]] = None,
    ) -> None:
        """Load firmware into the node through TFTP over IPv6.

        Args:
            firmware_file: Path to the LFU firmware file.
            callback_progress: Optional callback receiving the acknowledged
                upload progress as a percentage.

        Raises:
            ILStateError: If the node is connected or is not in bootloader
                mode.
            FileNotFoundError: If the firmware file does not exist.
            ILFirmwareLoadError: If the firmware file is invalid or the TFTP
                transfer fails.
        """
        if self.is_connected:
            raise ILStateError("Cannot load firmware while the SDCP node is connected")

        if self.mode != NodeMode.BOOTLOADER:
            raise ILStateError("Cannot load firmware to an SDCP node in application mode")

        with TftpUploader(self.target, self.interface) as uploader:
            uploader.upload_file(
                firmware_file,
                callback_progress=callback_progress,
            )
