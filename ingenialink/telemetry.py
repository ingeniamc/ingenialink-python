import os
from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from threading import Event, Lock, Thread
from typing import Callable, Optional, Union

from ingenialink._rust import telemetry as rust_telemetry
from ingenialink.exceptions import ILRegisterAccessError
from ingenialink.register import Register
from ingenialink.servo import Servo
from ingenialink.utils._utils import dtype_length_bits

TelemetryDecoder = rust_telemetry.TelemetryDecoder
TelemetryParquetRecorder = rust_telemetry.TelemetryParquetRecorder
TelemetryArrowIpcSink = rust_telemetry.TelemetryArrowIpcSink


@dataclass(frozen=True)
class TelemetryDescriptor:
    """Describe the registers and limits of a telemetry service."""

    name: str
    max_channels: int
    data_buffer_size: int
    base_frequency_hz: int
    max_frequency_divider: int
    timestamp_size: int
    timestamp_frequency_hz: int
    frame_count_size: int
    status_reg_uid: str
    data_reg_uid: str
    sample_size_reg_uid: str
    enable_reg_uid: str
    frequency_divider_reg_uid: str
    adaptive_rate_reg_uid: str
    mapped_register_count_reg_uid: str
    mapped_register_prefix: str


class Telemetry:
    """Configure and read a telemetry service through a servo."""

    def __init__(
        self,
        servo: Servo,
        descriptor: TelemetryDescriptor,
    ) -> None:
        """Create a telemetry client for a servo."""
        self._servo = servo
        self._descriptor = descriptor
        self._frame_size: Optional[int] = None
        self._read_buffer_size: Optional[int] = None
        self._achieved_frequency: Optional[float] = None

    @property
    def descriptor(self) -> TelemetryDescriptor:
        """Telemetry service descriptor."""
        return self._descriptor

    @property
    def achieved_frequency(self) -> float:
        """Configured telemetry sampling frequency.

        Raises:
            RuntimeError: If telemetry has not been configured yet.
        """
        if self._achieved_frequency is None:
            raise RuntimeError("Telemetry must be configured before reading its frequency")
        return self._achieved_frequency

    def recommended_poll_interval(self, buffer_fill_ratio: float = 0.5) -> float:
        """Calculate a host poll interval from the configured telemetry buffer.

        Args:
            buffer_fill_ratio: Fraction of one read buffer to fill before polling.

        Returns:
            The estimated host poll interval in seconds.

        Raises:
            RuntimeError: If telemetry has not been configured yet.
            ValueError: If the buffer fill ratio is invalid.
        """
        if self._frame_size is None or self._read_buffer_size is None:
            raise RuntimeError("Telemetry must be configured before calculating its poll interval")
        if not 0 < buffer_fill_ratio <= 1:
            raise ValueError("Telemetry buffer fill ratio must be between 0 and 1")
        frames_per_read = max(
            1,
            (self._read_buffer_size - self._descriptor.frame_count_size) // self._frame_size,
        )
        return buffer_fill_ratio * frames_per_read / self.achieved_frequency

    def configure(
        self,
        registers: Sequence[Register],
        desired_frequency: float = 1_000,
        adaptive_rate: bool = True,
    ) -> float:
        """Configure mapped registers and sampling frequency.

        Args:
            registers: Register instances to sample, in payload order.
            desired_frequency: Requested telemetry sampling frequency in hertz.
                The closest achievable frequency is configured and returned.
            adaptive_rate: Whether firmware may adapt the sampling rate based on
                telemetry buffer occupancy.

        Returns:
            The closest achievable sampling frequency in hertz.

        Raises:
            ValueError: If the configuration is outside the firmware limits.
            RuntimeError: If a register has no telemetry mapping metadata.
        """
        if not registers or len(registers) > self._descriptor.max_channels:
            raise ValueError(f"Telemetry requires 1 to {self._descriptor.max_channels} registers")
        frequency_divider = self._frequency_to_divider(desired_frequency, self._descriptor)

        self.stop()
        self._servo.write(self._descriptor.mapped_register_count_reg_uid, 0, subnode=0)
        payload_size = 0
        for channel, register in enumerate(registers):
            if register.monitoring is None:
                raise RuntimeError(
                    f"Register {register.identifier} has no telemetry mapping metadata"
                )
            value_size = dtype_length_bits[register.dtype] // 8
            payload_size += value_size
            mapping = self._map_register_value(
                register.monitoring.subnode,
                register.monitoring.address,
                register.dtype.value,
                value_size,
            )
            self._servo.write(
                f"{self._descriptor.mapped_register_prefix}{channel}_MAP",
                mapping,
                subnode=0,
            )
        self._servo.write(self._descriptor.mapped_register_count_reg_uid, len(registers), subnode=0)
        self._servo.write(self._descriptor.frequency_divider_reg_uid, frequency_divider, subnode=0)
        self._servo.write(self._descriptor.adaptive_rate_reg_uid, int(adaptive_rate), subnode=0)
        self._frame_size = payload_size + self._descriptor.timestamp_size
        self._read_buffer_size = self._buffer_size_for(self._frame_size, self._descriptor)
        self._achieved_frequency = self._divider_to_frequency(frequency_divider, self._descriptor)
        return self._achieved_frequency

    def start(self) -> None:
        """Start telemetry sampling."""
        self._servo.write(self._descriptor.enable_reg_uid, 1, subnode=0)

    def stop(self) -> None:
        """Stop telemetry sampling."""
        self._servo.write(self._descriptor.enable_reg_uid, 0, subnode=0)

    def is_running(self) -> bool:
        """Return whether telemetry sampling is enabled.

        Returns:
            ``True`` when sampling is enabled.
        """
        return bool(self._servo.read(self._descriptor.status_reg_uid, subnode=0))

    def sample_size(self) -> int:
        """Return the packed register payload size of one telemetry frame.

        Returns:
            Number of register payload bytes, excluding the firmware timestamp.

        Raises:
            RuntimeError: If the firmware reports an invalid frame size.
        """
        frame_size = int(self._servo.read(self._descriptor.sample_size_reg_uid, subnode=0))
        if frame_size < self._descriptor.timestamp_size:
            raise RuntimeError("Telemetry sample size is smaller than its timestamp")
        return frame_size - self._descriptor.timestamp_size

    def read_access(self) -> bytes:
        """Read one raw telemetry complete-access response.

        Returns:
            The firmware frame-count header and packed timestamped frames.

        Raises:
            RuntimeError: If telemetry has not been configured yet.
        """
        if self._frame_size is None or self._read_buffer_size is None:
            raise RuntimeError("Telemetry must be configured before reading frames")
        return self._servo.read_complete_access(
            self._descriptor.data_reg_uid, subnode=0, buffer_size=self._read_buffer_size
        )

    @classmethod
    def _buffer_size_for(cls, frame_size: int, descriptor: TelemetryDescriptor) -> int:
        available = descriptor.data_buffer_size - descriptor.frame_count_size
        if frame_size >= available:
            return descriptor.frame_count_size + frame_size
        frame_count = available // frame_size
        return descriptor.frame_count_size + frame_count * frame_size

    @staticmethod
    def _map_register_value(subnode: int, address: int, dtype: int, size: int) -> int:
        """Encode a firmware telemetry mapping entry.

        Returns:
            The packed mapping value expected by the firmware.
        """
        data_high = address | subnode << 12
        data_low = dtype << 8 | size
        return (data_high << 16) | data_low

    @classmethod
    def _frequency_to_divider(cls, frequency_hz: float, descriptor: TelemetryDescriptor) -> int:
        """Convert a requested frequency to the nearest firmware divider.

        Returns:
            The nearest integer sampling divider.

        Raises:
            RuntimeError: If a frame size does not match the configured registers.

            ValueError: If the frequency cannot be represented by the firmware.
        """
        minimum_frequency = descriptor.base_frequency_hz / descriptor.max_frequency_divider
        if (
            not isfinite(frequency_hz)
            or frequency_hz < minimum_frequency
            or frequency_hz > descriptor.base_frequency_hz
        ):
            raise ValueError(
                f"Telemetry frequency must be between {minimum_frequency} and "
                f"{descriptor.base_frequency_hz} Hz"
            )
        return round(descriptor.base_frequency_hz / frequency_hz)

    @classmethod
    def _divider_to_frequency(
        cls, frequency_divider: int, descriptor: TelemetryDescriptor
    ) -> float:
        """Convert a firmware divider to its resulting sampling frequency.

        Returns:
            The sampling frequency in hertz.
        """
        return descriptor.base_frequency_hz / frequency_divider


class TelemetryReader:
    """Forward raw telemetry accesses to a downstream consumer."""

    def __init__(
        self,
        telemetry: Telemetry,
        poll_interval: Optional[float] = None,
        buffer_fill_ratio: float = 0.5,
        on_access: Optional[Callable[[bytes], object]] = None,
    ) -> None:
        if poll_interval is not None and poll_interval <= 0:
            raise ValueError("Telemetry poll interval must be positive")
        if on_access is None:
            raise ValueError("Telemetry reader requires an access callback")
        self._telemetry = telemetry
        self._on_access = on_access
        self._poll_interval = (
            poll_interval
            if poll_interval is not None
            else telemetry.recommended_poll_interval(buffer_fill_ratio)
        )
        self._stop_event = Event()
        self._error: Optional[BaseException] = None
        self._error_lock = Lock()
        self._reader_thread = Thread(
            target=self._read_loop, name="TelemetryReader-reader", daemon=True
        )

    @property
    def poll_interval(self) -> float:
        """Interval used between empty telemetry polls."""
        return self._poll_interval

    @property
    def error(self) -> Optional[BaseException]:
        """First polling or access-forwarding error."""
        with self._error_lock:
            return self._error

    def start(self) -> None:
        """Start forwarding raw telemetry accesses."""
        self._reader_thread.start()

    def stop(self) -> None:
        """Stop reading and wait for the reader thread to finish."""
        self._stop_event.set()
        if self._reader_thread.is_alive():
            self._reader_thread.join()

    def is_alive(self) -> bool:
        """Return whether the reader thread is still running."""
        return self._reader_thread.is_alive()

    def _read_loop(self) -> None:
        """Read and forward complete telemetry accesses."""
        frame_count_size = self._telemetry.descriptor.frame_count_size
        while not self._stop_event.is_set():
            try:
                access = self._telemetry.read_access()
                if len(access) < frame_count_size:
                    self._stop_event.wait(self._poll_interval)
                    continue
                frame_count = int.from_bytes(access[:frame_count_size], "little")
                if frame_count == 0:
                    self._stop_event.wait(self._poll_interval)
                    continue
                self._on_access(access)
            except ILRegisterAccessError:  # noqa: PERF203
                self._stop_event.wait(self._poll_interval)
            except Exception as ex:
                self._set_error(ex)
                return

    def _set_error(self, ex: BaseException) -> None:
        """Record the first error and stop polling."""
        with self._error_lock:
            if self._error is None:
                self._error = ex
        self._stop_event.set()


class TelemetrySession:
    """Coordinate transport reading, decoding, and telemetry sinks.

    Python owns only transport. Rust owns decoding, batching, file
    output, streaming, metadata, and recording lifecycle state.
    """

    TIMESTAMP_COLUMN = "timestamp"
    DRIVE_TIMESTAMP_COLUMN = "drive_timestamp"
    TIMESTAMP_SEGMENT_COLUMN = "timestamp_segment"
    HOST_TIME_COLUMN = "host_time"
    FORMAT_VERSION = "2"
    METADATA_FORMAT_VERSION_KEY = "ingenialink.telemetry.format_version"
    METADATA_START_TIME_KEY = "ingenialink.telemetry.recording_start_utc"
    METADATA_TICK_FREQUENCY_KEY = "ingenialink.telemetry.timestamp_tick_frequency_hz"
    METADATA_REQUESTED_FREQUENCY_KEY = "ingenialink.telemetry.requested_frequency_hz"
    METADATA_ACHIEVED_FREQUENCY_KEY = "ingenialink.telemetry.achieved_frequency_hz"
    METADATA_MARKERS_KEY = "ingenialink.telemetry.markers"

    def __init__(
        self,
        servo: Servo,
        registers: Sequence[Register],
        path: Union[str, "os.PathLike[str]"],
        frequency: float = 1_000,
        batch_size: int = 1_000,
        poll_interval: Optional[float] = None,
        adaptive_rate: bool = True,
        *,
        buffer_fill_ratio: float = 0.5,
        ipc_address: Optional[str] = None,
    ) -> None:
        self._servo = servo
        self._registers = tuple(registers)
        self._path = path
        self._frequency = frequency
        self._batch_size = batch_size
        self._poll_interval = poll_interval
        self._adaptive_rate = adaptive_rate
        self._telemetry = servo.telemetry()
        self._descriptor = self._telemetry.descriptor
        self._buffer_fill_ratio = buffer_fill_ratio
        self._ipc_address = ipc_address
        self._ipc_sink_address: Optional[str] = None
        self._rust_decoder: Optional[TelemetryDecoder] = None
        self._reader: Optional[TelemetryReader] = None
        self._achieved_frequency: Optional[float] = None
        self._connection_epoch = 0
        self._error: Optional[BaseException] = None
        self._error_lock = Lock()

    @property
    def is_recording(self) -> bool:
        """Whether the transport loop is currently active."""
        return self._reader is not None and self._reader.is_alive()

    @property
    def error(self) -> Optional[BaseException]:
        """First transport or recording error."""
        with self._error_lock:
            return self._error

    @property
    def ipc_address(self) -> Optional[str]:
        """Listening address of the live Arrow IPC sink, if enabled."""
        return self._ipc_sink_address

    def start(self) -> None:
        """Configure and start transport feeding into the Rust recorder.

        Raises:
            RuntimeError: If recording is already active.
        """
        if self.is_recording:
            raise RuntimeError("Telemetry recorder is already running")
        self._achieved_frequency = self._telemetry.configure(
            self._registers,
            desired_frequency=self._frequency,
            adaptive_rate=self._adaptive_rate,
        )
        assert self._achieved_frequency is not None
        for register in self._registers:
            if register.monitoring is None:
                raise RuntimeError(
                    f"Register {register.identifier} has no telemetry mapping metadata"
                )
        if self._rust_decoder is None:
            channel_specs = [
                (register.identifier, register.dtype.name) for register in self._registers
            ]
            recorder = TelemetryParquetRecorder(
                os.fspath(self._path),
                channel_specs,
                self._descriptor.timestamp_frequency_hz,
                self._frequency,
                self._achieved_frequency,
                self._batch_size,
            )
            self._rust_decoder = TelemetryDecoder(
                channel_specs,
                self._descriptor.timestamp_frequency_hz,
                self._batch_size,
            )
            self._rust_decoder.attach_sink(recorder)
            if self._ipc_address is not None:
                ipc_sink = TelemetryArrowIpcSink(
                    self._ipc_address,
                    channel_specs,
                    self._descriptor.timestamp_frequency_hz,
                    self._frequency,
                    self._achieved_frequency,
                )
                self._ipc_sink_address = ipc_sink.address
                self._rust_decoder.attach_ipc_sink(ipc_sink)
        self._poll_interval = self._poll_interval or self._telemetry.recommended_poll_interval(
            self._buffer_fill_ratio
        )
        self._error = None
        self._reader = TelemetryReader(
            self._telemetry,
            self._poll_interval,
            self._buffer_fill_ratio,
            on_access=self._rust_decoder.feed,
        )
        self._poll_interval = self._reader.poll_interval
        self._telemetry.start()
        self._reader.start()

    def pause(self) -> None:
        """Stop transport feeding while keeping the Rust Parquet file open.

        Raises:
            RuntimeError: If recording is not active or failed.
        """
        if not self.is_recording or self._reader is None:
            raise RuntimeError("Telemetry recorder is not running")
        self._telemetry.stop()
        reader = self._reader
        reader.stop()
        self._reader = None
        if self._rust_decoder is not None:
            self._rust_decoder.flush()
        if reader.error is not None:
            self._error = reader.error
            raise RuntimeError("Telemetry recording failed") from reader.error

    def stop(self) -> None:
        """Stop transport and close the Rust Parquet file."""
        if self.is_recording:
            self.pause()
        if self._rust_decoder is not None:
            self._rust_decoder.stop()
            self._rust_decoder = None

    def add_marker(self, label: str, timestamp: Optional[float] = None) -> None:
        """Add a marker to Rust-owned Parquet metadata.

        Raises:
            RuntimeError: If recording has not started or has no timestamp.
        """
        if self._rust_decoder is None:
            raise RuntimeError("Telemetry recorder has not started recording")
        self._rust_decoder.add_marker(label, timestamp, self._connection_epoch)

    def rebind(self, servo: Servo) -> None:
        """Switch transport to a replacement servo connection.

        Raises:
            RuntimeError: If recording has not started.
        """
        if self._rust_decoder is None:
            raise RuntimeError("Telemetry recorder is not running")
        if self.is_recording:
            self.pause()
        self._servo = servo
        self._telemetry = servo.telemetry()
        self._descriptor = self._telemetry.descriptor
        self._connection_epoch += 1
        self.start()

    def __enter__(self) -> "TelemetrySession":
        """Start and return this recorder.

        Returns:
            The active recorder.
        """
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Stop and finalize the recording."""
        self.stop()
