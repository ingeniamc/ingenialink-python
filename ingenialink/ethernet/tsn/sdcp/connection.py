import socket
from contextlib import suppress
from types import TracebackType
from typing import Optional, Union

from ingenialink.ethernet.tsn.interfaces import get_interface_index
from ingenialink.ethernet.tsn.types import IPv6SocketAddress
from ingenialink.exceptions import ILIOError, ILTimeoutError

from .messages import (
    SDCPDeserializer,
    SDCPErrorResponse,
    SDCPIdentificationResponse,
    SDCPReadResponse,
    SDCPRequest,
    SDCPResponse,
    SDCPSubscribeResponse,
    SDCPUnsubscribeResponse,
    SDCPWriteResponse,
)

DEFAULT_SDCP_TIMEOUT_S = 1.0


class SDCPConnection:
    """Execute SDCP transactions over UDP/IPv6.

    Args:
        address: IPv6 address of the SDCP device.
        interface: Network interface in the same format as
            :func:`ingenialink.ethernet.tsn.ipv6_discovery.discover_ipv6_devices`.
        timeout: Timeout in seconds for SDCP requests and responses.

    Raises:
        OSError: If the interface cannot be resolved.


    """

    _MAX_RESPONSE_SIZE = 65_535
    _ACYCLIC_PORT = 22_334

    def __init__(
        self,
        address: str,
        interface: str,
        timeout: float,
    ) -> None:
        interface_index = get_interface_index(interface)

        self._destination = IPv6SocketAddress(
            address,
            self._ACYCLIC_PORT,
            0,
            interface_index,
        )
        self._timeout = timeout
        self._closed = False

        socket_instance: Optional[socket.socket] = None
        try:
            socket_instance = socket.socket(
                socket.AF_INET6,
                socket.SOCK_DGRAM,
            )
            socket_instance.settimeout(timeout)
        except OSError as error:
            if socket_instance is not None:
                with suppress(OSError):
                    socket_instance.close()
            raise ILIOError("Could not create the SDCP socket") from error
        self._socket = socket_instance

        try:
            self._socket.connect(self._destination)
        except OSError as error:
            with suppress(OSError):
                self._socket.close()
            self._closed = True
            raise ILIOError(f"Could not connect to SDCP device {self._destination}") from error

    def request(self, request: SDCPRequest) -> SDCPResponse:
        """Send an SDCP request and return its validated response.

        Args:
            request: SDCP request to send.

        Returns:
            The deserialized SDCP response.

        Raises:
            ILIOError: If communication fails, the connection is closed,
                or the received frame is not a valid response.
            ILTimeoutError: If the request times out.

        The caller must serialize this method with any other operation on this
        connection.
        """
        self._ensure_open()

        try:
            self._socket.send(bytes(request))
            payload = self._socket.recv(self._MAX_RESPONSE_SIZE)
        except socket.timeout as error:
            raise ILTimeoutError(
                "Timed out waiting for an SDCP response from "
                f"{self._destination} after "
                f"{self._timeout} seconds"
            ) from error
        except OSError as error:
            raise ILIOError(
                f"SDCP communication with {self._destination} failed: {error}"
            ) from error

        try:
            response = SDCPDeserializer.deserialize(payload)
        except (TypeError, ValueError) as error:
            raise ILIOError(f"Invalid SDCP response: {error}") from error

        if not isinstance(
            response,
            (
                SDCPIdentificationResponse,
                SDCPReadResponse,
                SDCPWriteResponse,
                SDCPSubscribeResponse,
                SDCPUnsubscribeResponse,
                SDCPErrorResponse,
            ),
        ):
            raise ILIOError(f"Unexpected SDCP frame received as response: {response}")

        if response.transaction_id != request.transaction_id:
            raise ILIOError(
                "SDCP transaction ID mismatch: "
                f"expected 0x{request.transaction_id:04X}, "
                f"received 0x{response.transaction_id:04X}"
            )

        return response

    def close(self) -> None:
        """Close the UDP/IPv6 socket.

        Raises:
            ILIOError: If closing the socket fails.

        The caller must serialize this method with :meth:`request`.
        """
        if self._closed:
            return

        try:
            self._socket.close()
        except OSError as error:
            self._closed = True
            raise ILIOError("Could not close the SDCP socket") from error
        else:
            self._closed = True

    def __enter__(self) -> "SDCPConnection":
        """Enter the connection context.

        Returns:
            The open SDCP connection.

        Raises:
            ILIOError: If the connection is closed.
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
            raise ILIOError("The SDCP connection is closed")
