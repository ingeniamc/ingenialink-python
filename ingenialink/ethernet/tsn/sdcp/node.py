"""Representation of an SDCP node."""

import time
from pathlib import Path
from typing import Callable, Optional, Union

from ingenialink.enums.node import NodeMode
from ingenialink.ethernet.tsn.ipv6_tftp import TftpUploader
from ingenialink.ethernet.tsn.sdcp.connection import DEFAULT_SDCP_TIMEOUT_S
from ingenialink.ethernet.tsn.sdcp.discovery import SDCPNodeDiscovery
from ingenialink.ethernet.tsn.sdcp.identification import identify_sdcp_node
from ingenialink.ethernet.tsn.sdcp.servo import SDCPServo
from ingenialink.exceptions import ILError, ILFirmwareLoadError, ILStateError
from ingenialink.node import Node
from ingenialink.servo import Servo
from ingenialink.utils.timeout import Timeout

DEFAULT_FIRMWARE_RECOVERY_TIMEOUT_S = 30.0
FIRMWARE_RECOVERY_POLL_INTERVAL_S = 1.0


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
        """Current IPv6 address of the node."""
        return self._discovery.target

    @property
    def interface(self) -> str:
        """Network interface used to reach the node."""
        return self._discovery.interface

    @property
    def protocol_version(self) -> int:
        """Currently reported SDCP protocol version."""
        return self._discovery.protocol_version

    @property
    def serial_number(self) -> int:
        """Serial number of the physical drive."""
        return self._discovery.serial_number

    @property
    def product_code(self) -> int:
        """Product code of the physical drive."""
        return self._discovery.product_code

    @property
    def revision_number(self) -> int:
        """Currently reported firmware revision."""
        return self._discovery.revision_number

    @property
    def mode(self) -> NodeMode:
        """Current operating mode of the node."""
        return self._discovery.mode

    @property
    def servo(self) -> Optional[SDCPServo]:
        """Associated application servo, if connected."""
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
            servo_status_listener: Whether to start the servo status listener.
            disconnect_callback: Callback invoked when the servo is
                disconnected.
            connection_timeout: Timeout in seconds for SDCP transactions.

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
        recovery_timeout: float = DEFAULT_FIRMWARE_RECOVERY_TIMEOUT_S,
        recovery_poll_interval: float = FIRMWARE_RECOVERY_POLL_INTERVAL_S,
    ) -> None:
        """Load firmware and refresh the node after it reboots.

        Args:
            firmware_file: Path to the LFU firmware file.
            callback_progress: Optional callback receiving the acknowledged
                upload progress as a percentage.
            recovery_timeout: Maximum time to wait for the node to return in
                application mode.
            recovery_poll_interval: Delay between identification attempts.

        Raises:
            ILStateError: If the node is connected or is not in bootloader
                mode.
            ValueError: If a recovery argument is not greater than zero.
            FileNotFoundError: If the firmware file does not exist.
            ILFirmwareLoadError: If the firmware transfer fails or the node
                does not recover in application mode within the timeout.
        """
        if self.is_connected:
            raise ILStateError("Cannot load firmware while the SDCP node is connected")

        if self.mode != NodeMode.BOOTLOADER:
            raise ILStateError("Cannot load firmware to an SDCP node in application mode")

        if recovery_timeout <= 0:
            raise ValueError("Recovery timeout must be greater than zero")
        if recovery_poll_interval <= 0:
            raise ValueError("Recovery poll interval must be greater than zero")

        with TftpUploader(self.target, self.interface) as uploader:
            uploader.upload_file(
                firmware_file,
                callback_progress=callback_progress,
            )

        self._wait_for_recovery(
            timeout=recovery_timeout,
            poll_interval=recovery_poll_interval,
        )

    def _wait_for_recovery(self, timeout: float, poll_interval: float) -> None:
        """Wait for the node to reboot in application mode and refresh it.

        Args:
            timeout: Maximum time to wait for recovery.
            poll_interval: Delay between identification attempts.

        Raises:
            ILFirmwareLoadError: If the node does not recover in application
                mode within the timeout.
        """
        with Timeout(timeout) as recovery_timeout:
            while not recovery_timeout.has_expired:
                try:
                    discovery = identify_sdcp_node(
                        target=self.target,
                        interface=self.interface,
                        timeout=min(
                            DEFAULT_SDCP_TIMEOUT_S,
                            recovery_timeout.remaining_time_s,
                        ),
                    )
                except ILError:
                    discovery = None

                if discovery is not None and discovery.mode == NodeMode.APPLICATION:
                    self.update(discovery)
                    return

                if not recovery_timeout.has_expired:
                    time.sleep(
                        min(
                            poll_interval,
                            recovery_timeout.remaining_time_s,
                        )
                    )

        raise ILFirmwareLoadError(
            f"SDCP node {self.identity} did not recover within {timeout} seconds."
        )
