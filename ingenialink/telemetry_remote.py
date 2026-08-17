"""Python control plane for remotely managed telemetry sessions."""

from __future__ import annotations

import json
import socketserver
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from threading import Lock, Thread
from typing import TYPE_CHECKING, Literal, Protocol, Union, cast

from typing_extensions import NotRequired, TypedDict

from ingenialink.telemetry import TelemetrySession

if TYPE_CHECKING:
    from ingenialink.register import Register
    from ingenialink.servo import Servo


class TelemetryCommand(str, Enum):
    """Commands accepted by the telemetry control channel."""

    CONFIGURE = "configure"
    START = "start"
    PAUSE = "pause"
    STOP = "stop"
    STATUS = "status"
    ADD_MARKER = "add_marker"


class TelemetryState(str, Enum):
    """Lifecycle states reported by a remote telemetry session."""

    CONFIGURED = "configured"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


RequestId = Union[str, int]


class TelemetryStatusResponse(TypedDict):
    """Wire response containing telemetry status."""

    ok: Literal[True]
    state: str
    registers: list[str]
    frequency_hz: float | None
    control_address: str
    data_address: str | None
    id: NotRequired[RequestId]


class TelemetryErrorResponse(TypedDict):
    """Wire response containing a control error."""

    ok: Literal[False]
    error: str
    id: NotRequired[RequestId]


TelemetryResponse = Union[TelemetryStatusResponse, TelemetryErrorResponse]


class _ControlCommand(Protocol):
    """Reusable command handler owned by one remote session."""

    def execute(self, payload: Mapping[str, object]) -> TelemetryResponse:
        """Execute one request payload."""


@dataclass(frozen=True)
class SocketAddress:
    """Host and port for a telemetry socket endpoint."""

    host: str
    port: int

    @classmethod
    def parse(cls, value: str) -> SocketAddress:
        """Parse a ``host:port`` endpoint.

        Returns:
            Parsed socket endpoint.

        Raises:
            ValueError: If the endpoint is malformed.
        """
        try:
            host, port = value.rsplit(":", 1)
            return cls(host, int(port))
        except (TypeError, ValueError) as error:
            raise ValueError(f"Invalid telemetry socket address: {value}") from error

    @classmethod
    def from_server_address(cls, value: object) -> SocketAddress:
        """Create an endpoint from a ``socketserver`` address tuple.

        Returns:
            Parsed socket endpoint.

        Raises:
            ValueError: If the server address has an unsupported shape.
        """
        if not isinstance(value, tuple) or len(value) < 2:
            raise ValueError("Unsupported socket server address")
        host, port = value[:2]
        if isinstance(host, bytes):
            host = host.decode()
        if not isinstance(host, str) or not isinstance(port, int):
            raise ValueError("Unsupported socket server address")
        return cls(host, port)

    def as_text(self) -> str:
        """Return the endpoint in ``host:port`` form."""
        return f"{self.host}:{self.port}"


class ConfigureCommand:
    """Configure one telemetry generation."""

    class Request(TypedDict):
        """Wire request for selecting telemetry channels."""

        command: Literal["configure"]
        registers: list[str]
        frequency_hz: NotRequired[float]
        adaptive_rate: NotRequired[bool]

    class Response(TelemetryStatusResponse):
        """Wire response after configuration."""

    def __init__(self, session: TelemetryRemoteSession) -> None:
        self._session = session

    def execute(self, payload: Mapping[str, object]) -> Response:
        """Configure the session from one typed request payload.

        Returns:
            Configuration response.

        Raises:
            TypeError: If a request field has an invalid type.
            ValueError: If a required field or register is invalid.
        """
        if "registers" not in payload:
            raise ValueError("Control request requires registers")
        request = cast("ConfigureCommand.Request", payload)
        raw_registers = request["registers"]
        if not isinstance(raw_registers, list) or not all(
            isinstance(register, str) for register in raw_registers
        ):
            raise TypeError("configure registers must be a list of strings")
        registers = tuple(request["registers"])
        frequency_hz: float | int = 1_000
        if "frequency_hz" in request:
            frequency_hz = request["frequency_hz"]
        adaptive_rate = True
        if "adaptive_rate" in request:
            adaptive_rate = request["adaptive_rate"]
        if not isinstance(frequency_hz, (float, int)) or isinstance(frequency_hz, bool):
            raise TypeError("frequency_hz must be numeric")
        if not isinstance(adaptive_rate, bool):
            raise TypeError("adaptive_rate must be boolean")
        if not registers:
            raise ValueError("configure requires at least one register")
        try:
            resolved = tuple(self._session._register_by_identifier[name] for name in registers)
        except KeyError as error:
            raise ValueError(f"Unknown telemetry register: {error.args[0]}") from error
        if self._session._session is not None:
            self._session._session.stop()
            self._session._session = None
        self._session._configuration = _TelemetryConfiguration(
            resolved, float(frequency_hz), adaptive_rate
        )
        return self._session._status().as_payload()


class StartCommand:
    """Start the configured telemetry generation."""

    class Request(TypedDict):
        """Wire request for starting telemetry."""

        command: Literal["start"]

    class Response(TelemetryStatusResponse):
        """Wire response after starting telemetry."""

    def __init__(self, session: TelemetryRemoteSession) -> None:
        self._session = session

    def execute(self, _payload: Mapping[str, object]) -> Response:
        """Start acquisition on the supplied session.

        Returns:
            Start response.

        Raises:
            RuntimeError: If telemetry is already running or unconfigured.
        """
        if self._session._session is not None and self._session._session.is_recording:
            raise RuntimeError("Telemetry acquisition is already running")
        if self._session._configuration is None:
            raise RuntimeError("Telemetry must be configured before it can start")
        configuration = self._session._configuration
        telemetry_session = TelemetrySession(
            self._session._servo,
            configuration.registers,
            self._session._path,
            frequency=configuration.frequency_hz,
            batch_size=self._session._batch_size,
            adaptive_rate=configuration.adaptive_rate,
            ipc_address=self._session._data_address.as_text(),
        )
        telemetry_session.start()
        self._session._session = telemetry_session
        return self._session._status().as_payload()


class PauseCommand:
    """Pause the active telemetry generation."""

    class Request(TypedDict):
        """Wire request for pausing telemetry."""

        command: Literal["pause"]

    class Response(TelemetryStatusResponse):
        """Wire response after pausing telemetry."""

    def __init__(self, session: TelemetryRemoteSession) -> None:
        self._session = session

    def execute(self, _payload: Mapping[str, object]) -> Response:
        """Pause acquisition on the supplied session.

        Returns:
            Pause response.

        Raises:
            RuntimeError: If telemetry is not configured.
        """
        if self._session._session is None:
            raise RuntimeError("Telemetry acquisition is not configured")
        self._session._session.pause()
        return self._session._status().as_payload()


class StopCommand:
    """Stop the active telemetry generation."""

    class Request(TypedDict):
        """Wire request for stopping telemetry."""

        command: Literal["stop"]

    class Response(TelemetryStatusResponse):
        """Wire response after stopping telemetry."""

    def __init__(self, session: TelemetryRemoteSession) -> None:
        self._session = session

    def execute(self, _payload: Mapping[str, object]) -> Response:
        """Stop acquisition on the supplied session.

        Returns:
            Stop response.
        """
        if self._session._session is not None:
            self._session._session.stop()
            self._session._session = None
        return self._session._status().as_payload()


class StatusCommand:
    """Request current telemetry status."""

    class Request(TypedDict):
        """Wire request for reading telemetry status."""

        command: Literal["status"]

    class Response(TelemetryStatusResponse):
        """Wire telemetry status response."""

    def __init__(self, session: TelemetryRemoteSession) -> None:
        self._session = session

    def execute(self, _payload: Mapping[str, object]) -> Response:
        """Read status from the supplied session.

        Returns:
            Status response.
        """
        return self._session._status().as_payload()


class AddMarkerCommand:
    """Add a marker to the active recording."""

    class Request(TypedDict):
        """Wire request for adding a telemetry marker."""

        command: Literal["add_marker"]
        label: str
        timestamp: NotRequired[float | None]

    class Response(TelemetryStatusResponse):
        """Wire response after adding a marker."""

    def __init__(self, session: TelemetryRemoteSession) -> None:
        self._session = session

    def execute(self, payload: Mapping[str, object]) -> Response:
        """Add a marker through the supplied session.

        Returns:
            Marker response.

        Raises:
            RuntimeError: If telemetry is not configured.
            TypeError: If a marker field has an invalid type.
            ValueError: If the label field is absent.
        """
        if "label" not in payload:
            raise ValueError("Control request requires label")
        request = cast("AddMarkerCommand.Request", payload)
        label = request["label"]
        timestamp: float | None = None
        if "timestamp" in request:
            timestamp = request["timestamp"]
        if not isinstance(label, str):
            raise TypeError("add_marker label must be a string")
        if timestamp is not None and (
            not isinstance(timestamp, (float, int)) or isinstance(timestamp, bool)
        ):
            raise TypeError("timestamp must be numeric or null")
        if self._session._session is None:
            raise RuntimeError("Telemetry acquisition is not configured")
        self._session._session.add_marker(
            label, float(timestamp) if timestamp is not None else None
        )
        return self._session._status().as_payload()


@dataclass(frozen=True)
class TelemetryStatus:
    """Typed status returned by the telemetry control plane."""

    state: TelemetryState
    registers: tuple[str, ...]
    frequency_hz: float | None
    control_endpoint: SocketAddress
    data_endpoint: SocketAddress | None

    def as_payload(self) -> TelemetryStatusResponse:
        """Serialize status at the JSON protocol boundary.

        Returns:
            Typed JSON response payload.
        """
        return TelemetryStatusResponse(
            ok=True,
            state=self.state.value,
            registers=list(self.registers),
            frequency_hz=self.frequency_hz,
            control_address=self.control_endpoint.as_text(),
            data_address=(self.data_endpoint.as_text() if self.data_endpoint is not None else None),
        )


@dataclass(frozen=True)
class _TelemetryConfiguration:
    """Pending telemetry configuration selected by a remote client."""

    registers: tuple[Register, ...]
    frequency_hz: float
    adaptive_rate: bool


def parse_request(
    payload: object,
) -> tuple[RequestId | None, TelemetryCommand, Mapping[str, object]]:
    """Convert one JSON payload into a typed telemetry command.

    Returns:
        Request identifier, command discriminator, and command payload.

    Raises:
        TypeError: If the payload has an invalid JSON shape.
        ValueError: If the command field has an invalid value.
    """
    if not isinstance(payload, Mapping):
        raise TypeError("Control request must be a JSON object")
    request_id = payload["id"] if "id" in payload else None  # noqa: SIM401
    if request_id is not None and not isinstance(request_id, (str, int)):
        raise TypeError("Control request id must be a string or integer")
    if "command" not in payload:
        raise ValueError("Control request requires command")
    raw_command = payload["command"]
    if not isinstance(raw_command, str):
        raise TypeError("Control command must be a string")
    try:
        command = TelemetryCommand(raw_command)
    except ValueError as error:
        raise ValueError(f"Unknown telemetry control command: {raw_command}") from error
    return request_id, command, payload


class _ControlServer(socketserver.ThreadingTCPServer):
    """Threaded control server carrying newline-delimited JSON messages."""

    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: SocketAddress, session: TelemetryRemoteSession) -> None:
        self.remote_session = session
        super().__init__((address.host, address.port), _ControlRequestHandler)


class _ControlRequestHandler(socketserver.StreamRequestHandler):
    """Handle one or more control requests from a connected client."""

    def handle(self) -> None:
        """Read requests and write one response per request."""
        session = self.server.remote_session  # type: ignore[attr-defined]
        while True:
            line = self.rfile.readline()
            if not line:
                return
            try:
                request_id, command, payload = parse_request(json.loads(line))
                response: TelemetryResponse = session.handle_command(command, payload)
                if request_id is not None:
                    response["id"] = request_id
            except (AttributeError, TypeError, ValueError, RuntimeError) as error:
                response = TelemetryErrorResponse({"ok": False, "error": str(error)})
            self.wfile.write(json.dumps(response, separators=(",", ":")).encode() + b"\n")
            self.wfile.flush()


class TelemetryRemoteSession:
    """Manage one telemetry generation through a typed control socket."""

    def __init__(
        self,
        servo: Servo,
        registers: tuple[Register, ...] | list[Register],
        path: str,
        *,
        control_address: str = "127.0.0.1:0",
        data_address: str = "127.0.0.1:0",
        frequency: float = 1_000,
        batch_size: int = 1_000,
        adaptive_rate: bool = True,
    ) -> None:
        """Create a remote telemetry controller.

        Args:
            servo: Servo providing the telemetry service.
            registers: Registers that remote clients may select.
            path: Parquet output path for the active acquisition.
            control_address: Host and port for the control socket.
            data_address: Host and port for the Arrow IPC socket.
            frequency: Default telemetry sampling frequency in hertz.
            batch_size: Samples per Arrow/Parquet batch.
            adaptive_rate: Whether firmware may adapt the sampling rate.

        Raises:
            ValueError: If register identifiers are duplicated or an address is invalid.
        """
        self._servo = servo
        self._register_by_identifier = self._index_registers(tuple(registers))
        self._path = path
        self._data_address = SocketAddress.parse(data_address)
        self._batch_size = batch_size
        self._lock = Lock()
        self._session: TelemetrySession | None = None
        self._configuration: _TelemetryConfiguration | None = _TelemetryConfiguration(
            tuple(registers), frequency, adaptive_rate
        )
        control_endpoint = SocketAddress.parse(control_address)
        self._server = _ControlServer(control_endpoint, self)
        self.control_endpoint = SocketAddress.from_server_address(self._server.server_address)
        self._commands: dict[TelemetryCommand, _ControlCommand] = {
            TelemetryCommand.CONFIGURE: ConfigureCommand(self),
            TelemetryCommand.START: StartCommand(self),
            TelemetryCommand.PAUSE: PauseCommand(self),
            TelemetryCommand.STOP: StopCommand(self),
            TelemetryCommand.STATUS: StatusCommand(self),
            TelemetryCommand.ADD_MARKER: AddMarkerCommand(self),
        }
        self._server_thread: Thread | None = None

    @staticmethod
    def _index_registers(registers: tuple[Register, ...]) -> dict[str, Register]:
        """Index the allowed registers by identifier.

        Returns:
            Register lookup keyed by identifier.

        Raises:
            ValueError: If an identifier occurs more than once.
        """
        indexed: dict[str, Register] = {}
        for register in registers:
            if register.identifier in indexed:
                raise ValueError(f"Duplicate telemetry register identifier: {register.identifier}")
            indexed[register.identifier] = register
        return indexed

    def start(self) -> None:
        """Start accepting remote control connections.

        Raises:
            RuntimeError: If the control server is already running.
        """
        if self._server_thread is not None and self._server_thread.is_alive():
            raise RuntimeError("Telemetry remote session is already running")
        self._server_thread = Thread(
            target=self._server.serve_forever,
            name="TelemetryRemoteSession-control",
            daemon=True,
        )
        self._server_thread.start()

    def stop(self) -> None:
        """Stop acquisition and close the control socket."""
        with self._lock:
            if self._session is not None:
                self._session.stop()
                self._session = None
        if self._server_thread is not None:
            self._server.shutdown()
            self._server_thread.join()
            self._server_thread = None
        self._server.server_close()

    def handle_command(
        self, command: TelemetryCommand, payload: Mapping[str, object]
    ) -> TelemetryResponse:
        """Execute one typed command against this session.

        Returns:
            Updated typed telemetry status.
        """
        with self._lock:
            return self._commands[command].execute(payload)

    def _status(self) -> TelemetryStatus:
        """Return the current typed remote-session state."""
        if self._configuration is None:
            state = TelemetryState.STOPPED
            registers: tuple[str, ...] = ()
            frequency_hz = None
        else:
            registers = tuple(register.identifier for register in self._configuration.registers)
            frequency_hz = self._configuration.frequency_hz
            state = (
                TelemetryState.RUNNING
                if self._session is not None and self._session.is_recording
                else TelemetryState.PAUSED
                if self._session is not None
                else TelemetryState.CONFIGURED
            )
        data_endpoint = None
        if self._session is not None and self._session.ipc_address is not None:
            data_endpoint = SocketAddress.parse(self._session.ipc_address)
        return TelemetryStatus(state, registers, frequency_hz, self.control_endpoint, data_endpoint)
