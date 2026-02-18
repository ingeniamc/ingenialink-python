import pickle
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock
from typing import Any, Callable, TypeVar

import ingenialogger

from ingenialink.constants import ETH_BUF_SIZE
from ingenialink.exceptions import ILIOError, ILTimeoutError

logger = ingenialogger.get_logger(__name__)

T = TypeVar("T")


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

    def receive_frame(self, recv_buffer_size: int = ETH_BUF_SIZE) -> bytes:
        """Receive a raw frame from the virtual drive.

        Args:
            recv_buffer_size: Maximum frame size in bytes.

        Raises:
            ILTimeoutError: If the receive operation times out.
            ILIOError: If there is an error receiving the data.

        Returns:
            The received frame bytes.

        """
        try:
            return self._socket.recv(recv_buffer_size)
        except socket.timeout as e:
            raise ILTimeoutError("Timeout while receiving data.") from e
        except OSError as e:
            raise ILIOError("Error receiving data.") from e

    def exchange_frame(self, frame: bytes, recv_buffer_size: int = ETH_BUF_SIZE) -> bytes:
        """Send a frame and return the response frame.

        Args:
            frame: Frame bytes to send.
            recv_buffer_size: Maximum frame size in bytes.

        Returns:
            The received frame bytes.

        """
        with self.transaction():
            self.send_frame(frame)
            return self.receive_frame(recv_buffer_size)

    def exchange_serialized_frame(
        self,
        frame_data: Any,
        deserialize_response: Callable[[Any], T],
        recv_buffer_size: int = ETH_BUF_SIZE,
    ) -> T:
        """Send a serialized python object frame and deserialize its response.

        Args:
            frame_data: Serializable request object to send.
            deserialize_response: Callable used to deserialize the response object.
            recv_buffer_size: Maximum frame size in bytes.

        Raises:
            ILIOError: If the response cannot be deserialized.

        Returns:
            Deserialized response value.

        """
        with self.transaction():
            self.send_frame(pickle.dumps(frame_data))
            response_frame = self.receive_frame(recv_buffer_size)
        try:
            response = pickle.loads(response_frame)
        except (pickle.UnpicklingError, EOFError, AttributeError, ValueError, TypeError) as e:
            raise ILIOError("Error deserializing response data.") from e
        return deserialize_response(response)
