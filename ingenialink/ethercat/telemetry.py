import json
import time
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from threading import Event, Lock, Thread
from types import ModuleType
from typing import TYPE_CHECKING, Optional, Union

from ingenialink.enums.register import RegDtype
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.exceptions import ILRegisterAccessError
from ingenialink.register import Register
from ingenialink.utils._utils import REG_VALUE, dtype_length_bits

if TYPE_CHECKING:
    import os

    import pyarrow as pa  # type: ignore[import-untyped]


@dataclass(frozen=True)
class TelemetryFrame:
    """One telemetry payload and its firmware sampling timestamp."""

    data: bytes
    timestamp_tick: int


@dataclass(frozen=True)
class TelemetrySample:
    """Decoded telemetry register values captured at one instant."""

    timestamp: float
    values: tuple[REG_VALUE, ...]


class EthercatTelemetry:
    """Configure and read the CoMoCo EtherCAT telemetry service."""

    MAX_CHANNELS = 16
    DATA_BUFFER_SIZE = 8 * 1024
    BASE_FREQUENCY_HZ = 1_000_000
    MAX_FREQUENCY_DIVIDER = 0xFFFF
    TIMESTAMP_SIZE = 8
    TIMESTAMP_FREQUENCY_HZ = 1_000_000
    FRAME_COUNT_SIZE = 2
    STATUS_REGISTER = "TEL_STATUS"
    DATA_REGISTER = "TEL_DATA_VALUE"
    SAMPLE_SIZE_REGISTER = "TEL_CFG_BYTES_VALUE"
    ENABLE_REGISTER = "TEL_ENABLE"
    FREQUENCY_DIVIDER_REGISTER = "TEL_FREQ_DIV"
    ADAPTIVE_RATE_REGISTER = "TEL_ADAPTIVE_RATE"
    MAPPED_REGISTER_COUNT_REGISTER = "TEL_CFG_TOTAL_MAP"
    MAPPED_REGISTER_PREFIX = "TEL_CFG_REG"

    def __init__(self, servo: EthercatServo) -> None:
        """Create a telemetry client for an EtherCAT servo."""
        self._servo = servo
        self._pending_frames: list[TelemetryFrame] = []
        self._frame_size: Optional[int] = None
        self._read_buffer_size: Optional[int] = None

    def configure(
        self,
        registers: Sequence[Register],
        desired_frequency: float = 1_000,
        adaptive_rate: bool = False,
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
        if not registers or len(registers) > self.MAX_CHANNELS:
            raise ValueError(f"Telemetry requires 1 to {self.MAX_CHANNELS} registers")
        frequency_divider = self._frequency_to_divider(desired_frequency)

        self.stop()
        self._servo.write(self.MAPPED_REGISTER_COUNT_REGISTER, 0, subnode=0)
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
            self._servo.write(f"{self.MAPPED_REGISTER_PREFIX}{channel}_MAP", mapping, subnode=0)
        self._servo.write(self.MAPPED_REGISTER_COUNT_REGISTER, len(registers), subnode=0)
        self._servo.write(self.FREQUENCY_DIVIDER_REGISTER, frequency_divider, subnode=0)
        self._servo.write(self.ADAPTIVE_RATE_REGISTER, int(adaptive_rate), subnode=0)
        self._frame_size = payload_size + self.TIMESTAMP_SIZE
        self._read_buffer_size = self._buffer_size_for(self._frame_size)
        self._pending_frames = []
        return self._divider_to_frequency(frequency_divider)

    def start(self) -> None:
        """Start telemetry sampling."""
        self._servo.write(self.ENABLE_REGISTER, 1, subnode=0)

    def stop(self) -> None:
        """Stop telemetry sampling."""
        self._servo.write(self.ENABLE_REGISTER, 0, subnode=0)

    def is_running(self) -> bool:
        """Return whether telemetry sampling is enabled.

        Returns:
            ``True`` when sampling is enabled.
        """
        return bool(self._servo.read(self.STATUS_REGISTER, subnode=0))

    def sample_size(self) -> int:
        """Return the packed register payload size of one telemetry frame.

        Returns:
            Number of register payload bytes, excluding the firmware timestamp.

        Raises:
            RuntimeError: If the firmware reports an invalid frame size.
        """
        frame_size = int(self._servo.read(self.SAMPLE_SIZE_REGISTER, subnode=0))
        if frame_size < self.TIMESTAMP_SIZE:
            raise RuntimeError("Telemetry sample size is smaller than its timestamp")
        return frame_size - self.TIMESTAMP_SIZE

    def read_frame(self) -> TelemetryFrame:
        """Read and remove the oldest queued telemetry frame.

        Returns:
            The oldest raw telemetry payload.

        Raises:
            RuntimeError: If the firmware frame does not contain a timestamp.
        """
        if self._pending_frames:
            return self._pending_frames.pop(0)

        frames = self._read_frames_from_servo()
        if not frames:
            raise RuntimeError("Telemetry frame does not contain a firmware timestamp")
        self._pending_frames.extend(frames[1:])
        return frames[0]

    def read_frames(self) -> list[TelemetryFrame]:
        """Read all complete telemetry frames returned by one EtherCAT access.

        Returns:
            Timestamped frames in chronological queue order.
        """
        frames = self._pending_frames
        new_frames = self._read_frames_from_servo()
        self._pending_frames = []
        frames.extend(new_frames)
        return frames

    def _read_frames_from_servo(self) -> list[TelemetryFrame]:
        """Read and decode the batch returned by the telemetry register.

        Returns:
            Timestamped frames in chronological queue order.

        Raises:
            RuntimeError: If the response declares unavailable frame bytes.
        """
        assert self._frame_size is not None, "configure() must be called before reading frames"
        frame_size = self._frame_size
        data = self._servo.read_complete_access(
            self.DATA_REGISTER, subnode=0, buffer_size=self._read_buffer_size
        )
        if len(data) < self.FRAME_COUNT_SIZE:
            return []
        frame_count = int.from_bytes(data[: self.FRAME_COUNT_SIZE], "little")
        expected_size = self.FRAME_COUNT_SIZE + frame_count * frame_size
        if len(data) < expected_size:
            raise RuntimeError(
                f"Telemetry read declared {frame_count} frames ({expected_size} bytes) "
                f"but only received {len(data)} bytes"
            )
        return [
            TelemetryFrame(
                data=data[offset + self.TIMESTAMP_SIZE : offset + frame_size],
                timestamp_tick=int.from_bytes(
                    data[offset : offset + self.TIMESTAMP_SIZE], "little"
                ),
            )
            for offset in range(
                self.FRAME_COUNT_SIZE,
                self.FRAME_COUNT_SIZE + frame_count * frame_size,
                frame_size,
            )
        ]

    @classmethod
    def _buffer_size_for(cls, frame_size: int) -> int:
        available = cls.DATA_BUFFER_SIZE - cls.FRAME_COUNT_SIZE
        if frame_size >= available:
            return cls.FRAME_COUNT_SIZE + frame_size
        frame_count = available // frame_size
        return cls.FRAME_COUNT_SIZE + frame_count * frame_size

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
    def _frequency_to_divider(cls, frequency_hz: float) -> int:
        """Convert a requested frequency to the nearest firmware divider.

        Returns:
            The nearest integer sampling divider.

        Raises:
            RuntimeError: If a frame size does not match the configured registers.

            ValueError: If the frequency cannot be represented by the firmware.
        """
        minimum_frequency = cls.BASE_FREQUENCY_HZ / cls.MAX_FREQUENCY_DIVIDER
        if (
            not isfinite(frequency_hz)
            or frequency_hz < minimum_frequency
            or frequency_hz > cls.BASE_FREQUENCY_HZ
        ):
            raise ValueError(
                f"Telemetry frequency must be between {minimum_frequency} and "
                f"{cls.BASE_FREQUENCY_HZ} Hz"
            )
        return round(cls.BASE_FREQUENCY_HZ / frequency_hz)

    @classmethod
    def _divider_to_frequency(cls, frequency_divider: int) -> float:
        """Convert a firmware divider to its resulting sampling frequency.

        Returns:
            The sampling frequency in hertz.
        """
        return cls.BASE_FREQUENCY_HZ / frequency_divider


class TelemetryPoller:
    """Poll decoded telemetry samples using separate reader and decoder threads.

    The reader thread performs complete-access reads and enqueues raw
    :class:`TelemetryFrame` objects as soon as they arrive, draining the
    device repeatedly while frames are available so a busy decoder never
    delays the next read. The decoder thread independently consumes that
    queue, validates and decodes each frame, and publishes
    :class:`TelemetrySample` objects for :meth:`get_sample`.

    At high sampling frequencies, complete-access reads should release the
    GIL so the reader is not blocked behind Python-level work on other
    threads. Construct the owning ``EthercatNetwork`` with
    ``GilReleaseConfig(sdo_read_write=True)`` (or :meth:`GilReleaseConfig.always`)
    for high-rate telemetry capture.

    Args:
        telemetry: Configured EtherCAT telemetry service.
        registers: Registers mapped by :meth:`EthercatTelemetry.configure`.
        poll_interval: Delay after an empty read, and the idle recheck
            interval for both threads, in seconds.
    """

    def __init__(
        self,
        telemetry: EthercatTelemetry,
        registers: Sequence[Register],
        poll_interval: float = 0.01,
    ) -> None:
        if not registers:
            raise ValueError("Telemetry poller requires at least one register")
        if poll_interval <= 0:
            raise ValueError("Telemetry poll interval must be positive")
        self._telemetry = telemetry
        self._registers = tuple(registers)
        self._poll_interval = poll_interval

        layout: list[tuple[Register, int, int]] = []
        offset = 0
        for register in self._registers:
            size = dtype_length_bits[register.dtype] // 8
            layout.append((register, offset, size))
            offset += size
        self._layout: tuple[tuple[Register, int, int], ...] = tuple(layout)
        self._expected_frame_size = offset

        self._raw_frames: deque[TelemetryFrame] = deque()
        self._frame_available = Event()
        self._samples: deque[TelemetrySample] = deque()
        self._stop_event = Event()
        self._sample_count = 0
        self._error: Optional[BaseException] = None
        self._error_lock = Lock()
        self._reader_thread = Thread(
            target=self._read_loop, name="TelemetryPoller-reader", daemon=True
        )
        self._decoder_thread = Thread(
            target=self._decode_loop, name="TelemetryPoller-decoder", daemon=True
        )

    def start(self) -> None:
        """Start the reader and decoder threads."""
        self._reader_thread.start()
        self._decoder_thread.start()

    def stop(self) -> None:
        """Stop polling and wait for the reader and decoder threads to finish."""
        self._stop_event.set()
        self._frame_available.set()
        if self._reader_thread.is_alive():
            self._reader_thread.join()
        if self._decoder_thread.is_alive():
            self._decoder_thread.join()

    def is_alive(self) -> bool:
        """Return whether the reader or the decoder thread is still running."""
        return self._reader_thread.is_alive() or self._decoder_thread.is_alive()

    def _read_loop(self) -> None:
        """Drain raw telemetry frames as fast as the device produces them.

        Each cycle keeps reading while the device returns frames, and only
        waits for :attr:`_poll_interval` after an empty read. Any error other
        than a transient register-access failure stops both stages early and
        is stored on :attr:`error`.
        """
        while not self._stop_event.is_set():
            try:
                frames = self._telemetry.read_frames()
            except ILRegisterAccessError:  # noqa: PERF203
                self._stop_event.wait(self._poll_interval)
                continue
            except Exception as ex:
                self._set_error(ex)
                return
            if not frames:
                self._stop_event.wait(self._poll_interval)
                continue
            self._raw_frames.extend(frames)
            self._frame_available.set()

    def _decode_loop(self) -> None:
        """Decode queued raw frames into :class:`TelemetrySample` objects.

        Runs independently of the reader and never blocks it. Any error
        stops both stages early and is stored on :attr:`error`.
        """
        while True:
            if not self._frame_available.wait(timeout=self._poll_interval):
                if self._stop_event.is_set() and not self._raw_frames:
                    return
                continue
            self._frame_available.clear()
            try:
                while self._raw_frames:
                    self._decode_frame(self._raw_frames.popleft())
            except Exception as ex:
                self._set_error(ex)
                return
            if self._stop_event.is_set() and not self._raw_frames:
                return

    def _decode_frame(self, frame: TelemetryFrame) -> None:
        """Validate, decode, and enqueue one raw telemetry frame.

        Raises:
            RuntimeError: If a frame size does not match the configured registers.
        """
        if len(frame.data) != self._expected_frame_size:
            raise RuntimeError(
                f"Telemetry frame has {len(frame.data)} bytes; expected {self._expected_frame_size}"
            )
        view = memoryview(frame.data)
        values = tuple(
            register.bytes_to_value(view[offset : offset + size])
            for register, offset, size in self._layout
        )
        timestamp = frame.timestamp_tick / self._telemetry.TIMESTAMP_FREQUENCY_HZ
        self._samples.append(TelemetrySample(timestamp=timestamp, values=values))
        self._sample_count += 1

    def _set_error(self, ex: BaseException) -> None:
        """Record the first error and stop both stages."""
        with self._error_lock:
            if self._error is None:
                self._error = ex
        self._stop_event.set()

    def get_sample(self) -> Optional[TelemetrySample]:
        """Return the oldest queued sample, or ``None`` when the queue is empty."""
        try:
            return self._samples.popleft()
        except IndexError:
            return None

    @property
    def sample_count(self) -> int:
        """Number of decoded telemetry samples."""
        return self._sample_count

    @property
    def error(self) -> Optional[BaseException]:
        """Exception that stopped the reader or decoder thread early, if any."""
        with self._error_lock:
            return self._error


def _pyarrow_type(pa: ModuleType, dtype: RegDtype) -> "pa.DataType":
    """Return the pyarrow type matching a register dtype.

    Raises:
        ValueError: If the dtype has no Parquet column mapping.
    """
    try:
        return {
            RegDtype.U8: pa.uint8(),
            RegDtype.S8: pa.int8(),
            RegDtype.U16: pa.uint16(),
            RegDtype.S16: pa.int16(),
            RegDtype.U32: pa.uint32(),
            RegDtype.S32: pa.int32(),
            RegDtype.U64: pa.uint64(),
            RegDtype.S64: pa.int64(),
            RegDtype.FLOAT: pa.float32(),
            RegDtype.BOOL: pa.bool_(),
            RegDtype.BYTE_ARRAY_512: pa.binary(512),
        }[dtype]
    except KeyError:
        raise ValueError(f"Register dtype {dtype} has no Parquet column mapping") from None


class TelemetryRecorder:
    """Record polled telemetry samples to a Parquet file.

    For high-rate capture (5 kHz and above), construct the ``servo``'s
    owning ``EthercatNetwork`` with ``GilReleaseConfig(sdo_read_write=True)``
    (or :meth:`GilReleaseConfig.always`) so complete-access telemetry reads
    do not block other Python threads while the SDO transaction is pending.
    Without it, the default pysoem behavior may serialize the reader thread
    against unrelated Python-side work and reintroduce read timing jitter.
    """

    TIMESTAMP_COLUMN = "timestamp"
    HOST_TIME_COLUMN = "host_time"
    FORMAT_VERSION = "1"
    METADATA_FORMAT_VERSION_KEY = "ingenialink.telemetry.format_version"
    METADATA_START_TIME_KEY = "ingenialink.telemetry.recording_start_utc"
    METADATA_TICK_FREQUENCY_KEY = "ingenialink.telemetry.timestamp_tick_frequency_hz"
    METADATA_REQUESTED_FREQUENCY_KEY = "ingenialink.telemetry.requested_frequency_hz"
    METADATA_ACHIEVED_FREQUENCY_KEY = "ingenialink.telemetry.achieved_frequency_hz"
    METADATA_MARKERS_KEY = "ingenialink.telemetry.markers"

    def __init__(
        self,
        servo: EthercatServo,
        registers: Sequence[Register],
        path: Union[str, "os.PathLike[str]"],
        frequency: float = 1_000,
        batch_size: int = 1_000,
        poll_interval: float = 0.01,
        flush_interval: float = 5.0,
        adaptive_rate: bool = False,
    ) -> None:
        try:
            import pyarrow as pa  # noqa: PLC0415
            import pyarrow.parquet as pq  # type: ignore[import-untyped]  # noqa: PLC0415
        except ImportError as ex:
            raise ImportError(
                "TelemetryRecorder requires pyarrow. Install it with the "
                "'telemetry' extra, e.g. `pip install ingenialink[telemetry]`."
            ) from ex
        self._pa: ModuleType = pa
        self._pq: ModuleType = pq
        self._registers = tuple(registers)
        self._path = path
        self._frequency = frequency
        self._adaptive_rate = adaptive_rate
        self._batch_size = batch_size
        self._poll_interval = poll_interval
        self._flush_interval = flush_interval
        self._telemetry = EthercatTelemetry(servo)
        self._schema = pa.schema(
            [
                pa.field(self.TIMESTAMP_COLUMN, pa.float64()),
                pa.field(self.HOST_TIME_COLUMN, pa.float64(), nullable=True),
            ]
            + [
                pa.field(register.identifier, _pyarrow_type(pa, register.dtype))
                for register in self._registers
            ]
        )
        self._poller: Optional[TelemetryPoller] = None
        self._writer: Optional[pq.ParquetWriter] = None
        self._writer_lock = Lock()
        self._drain_thread: Optional[Thread] = None
        self._drain_error: Optional[BaseException] = None
        self._stop_drain = Event()
        self._markers: list[dict[str, object]] = []
        self._last_timestamp: Optional[float] = None

    @property
    def is_recording(self) -> bool:
        """Whether telemetry sampling is currently running."""
        return self._poller is not None

    def add_marker(self, label: str, timestamp: Optional[float] = None) -> None:
        """Record a labeled marker into the file's metadata, for viewers to display.

        Args:
            label: Short text describing the marker.
            timestamp: Position on the recording's timestamp column. Defaults
                to the timestamp of the most recently written sample.

        Raises:
            RuntimeError: If recording has not started, or no timestamp is
                given and no sample has been written yet.
        """
        with self._writer_lock:
            if self._writer is None:
                raise RuntimeError("Telemetry recorder has not started recording")
            resolved_timestamp = self._last_timestamp if timestamp is None else timestamp
            if resolved_timestamp is None:
                raise RuntimeError("No samples recorded yet; pass an explicit timestamp")
            self._markers.append({"time": resolved_timestamp, "label": label})
            self._writer.add_key_value_metadata(
                {self.METADATA_MARKERS_KEY: json.dumps(self._markers)}
            )

    def start(self) -> None:
        """Start recording, or resume it after :meth:`pause`.

        Raises:
            RuntimeError: If recording is already running.
        """
        if self.is_recording:
            raise RuntimeError("Telemetry recorder is already running")
        if self._writer is None:
            achieved_frequency = self._telemetry.configure(
                self._registers,
                desired_frequency=self._frequency,
                adaptive_rate=self._adaptive_rate,
            )
            schema = self._schema.with_metadata({
                self.METADATA_FORMAT_VERSION_KEY: self.FORMAT_VERSION,
                self.METADATA_START_TIME_KEY: datetime.now(timezone.utc).isoformat(),
                self.METADATA_TICK_FREQUENCY_KEY: str(self._telemetry.TIMESTAMP_FREQUENCY_HZ),
                self.METADATA_REQUESTED_FREQUENCY_KEY: str(self._frequency),
                self.METADATA_ACHIEVED_FREQUENCY_KEY: str(achieved_frequency),
            })
            self._writer = self._pq.ParquetWriter(self._path, schema)
        poller = TelemetryPoller(self._telemetry, self._registers, self._poll_interval)
        self._poller = poller
        self._stop_drain.clear()
        self._telemetry.start()
        poller.start()
        self._drain_thread = Thread(target=self._drain_loop, args=(poller,), daemon=True)
        self._drain_thread.start()

    def pause(self) -> None:
        """Pause recording without closing the output file.

        Raises:
            RuntimeError: If recording is not running or a recording error occurred.
        """
        if self._poller is None or self._drain_thread is None:
            raise RuntimeError("Telemetry recorder is not running")
        poller = self._poller
        drain_thread = self._drain_thread
        self._telemetry.stop()
        poller.stop()
        self._poller = None
        self._stop_drain.set()
        drain_thread.join()
        self._drain_thread = None
        error = self._drain_error or poller.error
        self._drain_error = None
        if error is not None:
            raise RuntimeError("Telemetry recording failed") from error

    def stop(self) -> None:
        """Stop recording and finalize the Parquet file."""
        pause_error: Optional[RuntimeError] = None
        if self.is_recording:
            try:
                self.pause()
            except RuntimeError as ex:
                pause_error = ex
        if self._writer is not None:
            with self._writer_lock:
                self._writer.close()
            self._writer = None
        if pause_error is not None:
            raise pause_error

    def __enter__(self) -> "TelemetryRecorder":
        """Start recording and return this recorder.

        Returns:
            This recorder.
        """
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Stop recording and finalize the output file."""
        self.stop()

    def _drain_loop(self, poller: TelemetryPoller) -> None:
        buffer: list[TelemetrySample] = []
        last_flush = time.monotonic()
        while not self._stop_drain.is_set():
            sample = poller.get_sample()
            if sample is None:
                if buffer and time.monotonic() - last_flush >= self._flush_interval:
                    if not self._flush(buffer):
                        return
                    buffer = []
                    last_flush = time.monotonic()
                self._stop_drain.wait(self._poll_interval)
                continue
            buffer.append(sample)
            self._last_timestamp = sample.timestamp
            if len(buffer) >= self._batch_size:
                if not self._flush(buffer):
                    return
                buffer = []
                last_flush = time.monotonic()
        while (sample := poller.get_sample()) is not None:
            buffer.append(sample)
            self._last_timestamp = sample.timestamp
        if buffer:
            self._flush(buffer)

    def _flush(self, samples: list[TelemetrySample]) -> bool:
        try:
            self._write_batch(samples)
        except Exception as ex:
            self._drain_error = ex
            return False
        return True

    def _write_batch(self, samples: list[TelemetrySample]) -> None:
        assert self._writer is not None
        host_times: list[Optional[float]] = [None] * len(samples)
        host_times[0] = time.time()
        arrays = [
            self._pa.array([sample.timestamp for sample in samples], type=self._pa.float64()),
            self._pa.array(host_times, type=self._pa.float64()),
        ]
        arrays.extend(
            self._pa.array(
                [sample.values[index] for sample in samples],
                type=_pyarrow_type(self._pa, register.dtype),
            )
            for index, register in enumerate(self._registers)
        )
        table = self._pa.Table.from_arrays(arrays, schema=self._schema)
        with self._writer_lock:
            self._writer.write_table(table)
