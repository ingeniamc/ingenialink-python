"""Base node abstraction."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Generic, Optional, TypeVar, Union

from ingenialink.enums.node import NodeMode
from ingenialink.servo import Servo

DiscoveryT = TypeVar("DiscoveryT")
ServoT = TypeVar("ServoT", bound=Servo)

NodeIdentity = tuple[int, int]


class Node(ABC, Generic[DiscoveryT, ServoT]):
    """Base representation of a physical drive managed by a network.

    A node preserves the identity and latest discovery state of a physical
    drive independently of an active application connection.
    """

    @property
    def identity(self) -> NodeIdentity:
        """Return the stable identity of the physical drive."""
        return self.product_code, self.serial_number

    @property
    @abstractmethod
    def target(self) -> str:
        """Return the current network address of the node."""

    @property
    @abstractmethod
    def serial_number(self) -> int:
        """Return the serial number of the physical drive."""

    @property
    @abstractmethod
    def product_code(self) -> int:
        """Return the product code of the physical drive."""

    @property
    @abstractmethod
    def revision_number(self) -> int:
        """Return the currently reported firmware revision."""

    @property
    @abstractmethod
    def mode(self) -> NodeMode:
        """Return the current operating mode of the node."""

    @property
    @abstractmethod
    def servo(self) -> Optional[ServoT]:
        """Return the associated application servo, if connected."""

    @property
    def is_connected(self) -> bool:
        """Return whether an application servo is associated with the node."""
        return self.servo is not None

    @abstractmethod
    def update(self, discovery: DiscoveryT) -> None:
        """Update the node using the latest discovery information."""

    @abstractmethod
    def connect(
        self,
        dictionary_path: str,
        connection_timeout: float,
        servo_status_listener: bool = False,
        disconnect_callback: Optional[Callable[[Servo], None]] = None,
    ) -> ServoT:
        """Connect to the protocol-specific application servo."""

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect the associated application servo."""

    @abstractmethod
    def load_firmware(
        self,
        firmware_file: Union[str, Path],
        callback_progress: Optional[Callable[[int], None]] = None,
    ) -> None:
        """Load firmware using the protocol-specific transfer mechanism."""
