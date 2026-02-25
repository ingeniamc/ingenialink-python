import socket
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock

from ingenialink.exceptions import ILIOError, ILTimeoutError

VIRTUAL_DRIVE_RECV_BUFFER_SIZE = 2048


class VirtualServoBase:
    """Base class for shared virtual servo behavior."""

    def __init__(self, sock: socket.socket, lock: Lock) -> None:
        self._socket = sock
        self._lock = lock

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Acquire the communication lock for a full request/response transaction."""
        self._lock.acquire()
        try:
            yield
        finally:
            self._lock.release()

    def send_frame(self, frame: bytes) -> None:
        """Send a serialized frame to the virtual drive.

        Args:
            frame: Frame bytes to send.

        Raises:
            ILIOError: If there is an error sending the data.

        """
        try:
            self._socket.sendall(frame)
        except OSError as e:
            raise ILIOError("Error sending data.") from e

    def receive_frame(self) -> bytes:
        """Receive a raw frame from the virtual drive.

        Raises:
            ILTimeoutError: If the receive operation times out.
            ILIOError: If there is an error receiving the data.

        Returns:
            The received frame bytes.

        """
        try:
            return self._socket.recv(VIRTUAL_DRIVE_RECV_BUFFER_SIZE)
        except socket.timeout as e:
            raise ILTimeoutError("Timeout while receiving data.") from e
        except OSError as e:
            raise ILIOError("Error receiving data.") from e

    def exchange_frame(self, frame: bytes) -> bytes:
        """Send a frame and return the response frame.

        Args:
            frame: Frame bytes to send.

        Returns:
            The received frame bytes.

        """
        with self.transaction():
            self.send_frame(frame)
            return self.receive_frame()
