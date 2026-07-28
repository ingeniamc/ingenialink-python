"""Representation of a TSN node."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Union

from ingenialink.enums.node import NodeMode
from ingenialink.ethernet.tsn.connection import DEFAULT_SDCP_TIMEOUT_S
from ingenialink.ethernet.tsn.ipv6_tftp import TftpUploader
from ingenialink.ethernet.tsn.servo import TSNServo
from ingenialink.exceptions import ILStateError
from ingenialink.servo import Servo


@dataclass(frozen=True)
class TSNNodeDiscovery:
    """Information obtained while discovering a TSN node."""

    target: str
    interface: str
    protocol_version: int
    serial_number: int
    product_code: int
    revision_number: int
    mode: NodeMode


class TSNNode:
    """Representation of a physical TSN drive.

    A node preserves the identity and latest discovery information of a
    physical drive independently of its current operating mode or application
    connection.

    The product code and serial number form the stable drive identity. The
    endpoint, protocol version, revision number, and operating mode represent
    the latest discovery state and may change during the drive lifecycle.

    Args:
        discovery: Information obtained from the latest successful discovery.
    """

    def __init__(self, discovery: TSNNodeDiscovery) -> None:
        self._discovery = discovery
        self._servo: Optional[TSNServo] = None

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
    def servo(self) -> Optional[TSNServo]:
        """Return the associated application servo, if connected."""
        return self._servo

    @property
    def is_connected(self) -> bool:
        """Return whether an application servo is associated with the node."""
        return self._servo is not None

    def update(self, discovery: TSNNodeDiscovery) -> None:
        """Update the node with the latest discovery information.

        The product code and serial number cannot change because they identify
        the physical drive represented by this node.

        Args:
            discovery: Information obtained from the latest successful
                discovery.

        Raises:
            ValueError: If the discovery information belongs to a different
                physical drive.
            ILStateError: If the discovery information belongs to a different
                target, interface, or operating mode while the node is connected.
        """
        if (discovery.product_code, discovery.serial_number) != (
            self.product_code,
            self.serial_number,
        ):
            raise ValueError("Cannot update a TSN node with a different drive identity")

        if self.is_connected and (
            discovery.target != self.target
            or discovery.interface != self.interface
            or discovery.mode != self.mode
        ):
            raise ILStateError(
                "Cannot update the target, interface, or mode of a connected TSN node"
            )

        self._discovery = discovery

    def connect(
        self,
        dictionary_path: str,
        connection_timeout: float = DEFAULT_SDCP_TIMEOUT_S,
        servo_status_listener: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ) -> TSNServo:
        """Connect to the application servo.

        Args:
            dictionary_path: Path to the drive dictionary.
            connection_timeout: Timeout in seconds for SDCP transactions.
            servo_status_listener: Whether to start the servo status listener.
            disconnect_callback: Callback invoked when the servo is
                disconnected.

        Returns:
            The connected TSN servo.

        Raises:
            ILStateError: If the node is not in application mode or is already
                connected.
        """
        if self.mode != NodeMode.APPLICATION:
            raise ILStateError(f"Cannot connect to a TSN node in {self.mode.name.lower()} mode")

        if self.is_connected:
            raise ILStateError("The TSN node is already connected")

        self._servo = TSNServo(
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
            raise ILStateError("Cannot load firmware while the TSN node is connected")

        if self.mode != NodeMode.BOOTLOADER:
            raise ILStateError(
                f"Cannot load firmware to a TSN node in {self.mode.name.lower()} mode"
            )

        with TftpUploader(self.target, self.interface) as uploader:
            uploader.upload_file(
                firmware_file,
                callback_progress=callback_progress,
            )
