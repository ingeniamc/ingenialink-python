import socket
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock
from typing import Any

from ingenialink.exceptions import ILIOError, ILTimeoutError
from ingenialink.virtual.codec import deserialize_sdo_frame, serialize_sdo_frame
from ingenialink.constants import VIRTUAL_DRIVE_RECV_BUFFER_SIZE

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

    def exchange_sdo_frame(self, frame_data: dict[str, Any]) -> dict[str, Any]:
        """Send an SDO frame and return the deserialized response.

        Args:
            frame_data: SDO payload dictionary to send.

        Returns:
            The deserialized SDO response dictionary.

        Raises:
            ILIOError: If the response cannot be deserialized.

        """
        with self.transaction():
            self.send_frame(serialize_sdo_frame(frame_data))
            response_frame = self.receive_frame()

        try:
            return deserialize_sdo_frame(response_frame)
        except (UnicodeDecodeError, ValueError, TypeError) as e:
            raise ILIOError("Error deserializing SDO response data.") from e

    @staticmethod
    def deserialize_read_response(response: object) -> bytes:
        """Extract the data bytes from an SDO read response.

        Args:
            response: The deserialized SDO response.

        Returns:
            The data bytes from the response.

        Raises:
            ILIOError: If the response is unexpected or contains an error.

        """
        if isinstance(response, bytes):
            return response

        if isinstance(response, dict):
            if "error_code" in response:
                raise ILIOError(f"Error code {response['error_code']} received in read response")
            data = response.get("data")
            if isinstance(data, bytes):
                return data

        raise ILIOError(f"Unexpected response type for read operation: {type(response)}")

    @staticmethod
    def deserialize_write_response(response: object) -> None:
        """Validate an SDO write response.

        Args:
            response: The deserialized SDO response.

        Raises:
            ILIOError: If the response is unexpected or contains an error.

        """
        if not isinstance(response, dict):
            raise ILIOError(f"Unexpected response type for write operation: {type(response)}")
        if "error_code" in response:
            raise ILIOError(f"Error code {response['error_code']} received in write response")
        return None
