import socket
from threading import Lock
from types import TracebackType
from typing import Union

from .interfaces import get_interface_index
from .sdcp import (
    SDCPDeserializer,
    SDCPMessage,
)


class SDCPConnection:
    """Execute SDCP transactions over UDP/IPv6."""

    _MAX_RESPONSE_SIZE = 65_535
    _INITIAL_TRANSACTION_ID = 0x0
    _ACYCLIC_PORT = 22_334
    _CONNECTION_TIMEOUT_S = 2.0

    def __init__(
        self,
        address: str,
        interface: str,
        timeout: float = _CONNECTION_TIMEOUT_S,
    ) -> None:
        address = address.split("%", maxsplit=1)[0]
        interface_index = get_interface_index(interface)

        self._destination = (
            address,
            self._ACYCLIC_PORT,
            0,
            interface_index,
        )
        self._timeout = timeout
        self._transaction_id = self._INITIAL_TRANSACTION_ID
        self._lock = Lock()
        self._closed = False

        self._socket = socket.socket(
            socket.AF_INET6,
            socket.SOCK_DGRAM,
        )
        self._socket.settimeout(timeout)

        try:
            self._socket.connect(self._destination)
        except OSError:
            self._socket.close()
            self._closed = True
            raise

    def request(self, request: SDCPMessage) -> SDCPMessage:
        """Send an SDCP request and return its validated response.

        Returns:
            Deserialized SDCP response.

        Raises:
            RuntimeError: If the connection is closed, communication fails,
                the request times out, or the response is invalid.
        """
        with self._lock:
            self._ensure_open()

            try:
                self._socket.send(bytes(request))
                payload = self._socket.recv(self._MAX_RESPONSE_SIZE)
            except socket.timeout as error:
                raise RuntimeError(
                    "Timed out waiting for an SDCP response from "
                    f"{self._destination} after "
                    f"{self._timeout} seconds"
                ) from error
            except OSError as error:
                raise RuntimeError(
                    f"SDCP communication with {self._destination} failed: {error}"
                ) from error

            try:
                response = SDCPDeserializer.deserialize(payload)
            except (TypeError, ValueError) as error:
                raise RuntimeError(f"Invalid SDCP response: {error}") from error

            return response

    def close(self) -> None:
        """Close the UDP/IPv6 socket."""
        with self._lock:
            if self._closed:
                return

            self._socket.close()
            self._closed = True

    def __enter__(self) -> "SDCPConnection":
        """Enter the connection context.

        Returns:
            The open SDCP connection.

        Raises:
            RuntimeError: If the connection is closed.
        """
        self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type: Union[type[BaseException], None],
        exc_value: Union[BaseException, None],
        traceback: Union[TracebackType, None],
    ) -> None:
        """Close the connection when leaving the context."""
        self.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("The SDCP connection is closed")
