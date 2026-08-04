import queue
from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from threading import Event, Thread

from ingenialink.ethercat.servo import EthercatServo
from ingenialink.exceptions import ILRegisterAccessError
from ingenialink.register import Register
from ingenialink.utils._utils import REG_VALUE, dtype_length_bits


@dataclass(frozen=True)
class TelemetryFrame:
    """One telemetry payload and its firmware sampling timestamp."""

    data: bytes
    timestamp_tick: int


@dataclass(frozen=True)
class TelemetrySample:
    """Decoded telemetry register values captured at one instant."""

    timestamp: float
    values: dict[str, REG_VALUE]


class EthercatTelemetry:
    """Configure and read the CoMoCo EtherCAT telemetry service."""

    MAX_CHANNELS = 16
    DATA_BUFFER_SIZE = 1024
    BASE_FREQUENCY_HZ = 1_000_000
    MAX_FREQUENCY_DIVIDER = 0xFFFF
    TIMESTAMP_SIZE = 8
    TIMESTAMP_FREQUENCY_HZ = 1_000_000
    STATUS_REGISTER = "TEL_STATUS"
    DATA_REGISTER = "TEL_DATA_VALUE"
    SAMPLE_SIZE_REGISTER = "TEL_CFG_BYTES_VALUE"
    ENABLE_REGISTER = "TEL_ENABLE"
    FREQUENCY_DIVIDER_REGISTER = "TEL_FREQ_DIV"
    MAPPED_REGISTER_COUNT_REGISTER = "TEL_CFG_TOTAL_MAP"
    MAPPED_REGISTER_PREFIX = "TEL_CFG_REG"

    def __init__(self, servo: EthercatServo) -> None:
        """Create a telemetry client for an EtherCAT servo."""
        self._servo = servo
        self._pending_frames: list[TelemetryFrame] = []

    def configure(
        self,
        registers: Sequence[Register],
        desired_frequency: float = 1_000,
    ) -> float:
        """Configure mapped registers and sampling frequency.

        Args:
            registers: Register instances to sample, in payload order.
            desired_frequency: Requested telemetry sampling frequency in hertz.
                The closest achievable frequency is configured and returned.

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
        for channel, register in enumerate(registers):
            if register.monitoring is None:
                raise RuntimeError(
                    f"Register {register.identifier} has no telemetry mapping metadata"
                )
            value_size = dtype_length_bits[register.dtype] // 8
            mapping = self._map_register_value(
                register.monitoring.subnode,
                register.monitoring.address,
                register.dtype.value,
                value_size,
            )
            self._servo.write(f"{self.MAPPED_REGISTER_PREFIX}{channel}_MAP", mapping, subnode=0)
        self._servo.write(self.MAPPED_REGISTER_COUNT_REGISTER, len(registers), subnode=0)
        self._servo.write(self.FREQUENCY_DIVIDER_REGISTER, frequency_divider, subnode=0)
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
            RuntimeError: If the register contains an incomplete frame.
        """
        frame_size = self.sample_size() + self.TIMESTAMP_SIZE
        data = self._servo.read_complete_access(
            self.DATA_REGISTER, subnode=0, buffer_size=self.DATA_BUFFER_SIZE
        )
        if len(data) % frame_size != 0:
            raise RuntimeError("Telemetry data contains an incomplete frame")
        return [
            TelemetryFrame(
                data=data[offset + self.TIMESTAMP_SIZE : offset + frame_size],
                timestamp_tick=int.from_bytes(
                    data[offset : offset + self.TIMESTAMP_SIZE], "little"
                ),
            )
            for offset in range(0, len(data), frame_size)
        ]

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


class TelemetryPoller(Thread):
    """Poll decoded telemetry samples in a worker thread.

    Args:
        telemetry: Configured EtherCAT telemetry service.
        registers: Registers mapped by :meth:`EthercatTelemetry.configure`.
        poll_interval: Delay between empty polling attempts, in seconds.
        queue_size: Maximum number of samples retained for consumers.
    """

    def __init__(
        self,
        telemetry: EthercatTelemetry,
        registers: Sequence[Register],
        poll_interval: float = 0.01,
        queue_size: int = 1024,
    ) -> None:
        super().__init__(daemon=True)
        if not registers:
            raise ValueError("Telemetry poller requires at least one register")
        if poll_interval <= 0:
            raise ValueError("Telemetry poll interval must be positive")
        if queue_size <= 0:
            raise ValueError("Telemetry poller queue size must be positive")
        self._telemetry = telemetry
        self._registers = tuple(registers)
        self._poll_interval = poll_interval
        self._samples: queue.Queue[TelemetrySample] = queue.Queue(maxsize=queue_size)
        self._stop_event = Event()

    def run(self) -> None:
        """Poll frames and enqueue decoded register values.

        Raises:
            RuntimeError: If a frame size does not match the configured registers.
        """
        while not self._stop_event.is_set():
            try:
                frames = self._telemetry.read_frames()
            except ILRegisterAccessError:
                self._stop_event.wait(self._poll_interval)
                continue

            expected_size = sum(
                dtype_length_bits[register.dtype] // 8 for register in self._registers
            )
            for frame in frames:
                if len(frame.data) != expected_size:
                    raise RuntimeError(
                        f"Telemetry frame has {len(frame.data)} bytes; expected {expected_size}"
                    )
                values: dict[str, REG_VALUE] = {}
                offset = 0
                for register in self._registers:
                    size = dtype_length_bits[register.dtype] // 8
                    values[register.identifier] = register.bytes_to_value(
                        frame.data[offset : offset + size]
                    )
                    offset += size
                timestamp = frame.timestamp_tick / self._telemetry.TIMESTAMP_FREQUENCY_HZ
                self._enqueue(TelemetrySample(timestamp=timestamp, values=values))
            if not frames:
                self._stop_event.wait(self._poll_interval)

    def stop(self) -> None:
        """Stop polling and wait for the worker thread to finish."""
        self._stop_event.set()
        if self.is_alive():
            self.join()

    def get_sample(self) -> TelemetrySample | None:
        """Return the oldest queued sample, or ``None`` when the queue is empty."""
        try:
            return self._samples.get_nowait()
        except queue.Empty:
            return None

    def get_latest_sample(self) -> TelemetrySample | None:
        """Return the newest queued sample and discard older samples."""
        sample = self.get_sample()
        if sample is None:
            return None
        while True:
            newer_sample = self.get_sample()
            if newer_sample is None:
                return sample
            sample = newer_sample

    def _enqueue(self, sample: TelemetrySample) -> None:
        """Enqueue a sample, discarding the oldest one when the queue is full."""
        try:
            self._samples.put_nowait(sample)
        except queue.Full:
            self._samples.get_nowait()
            self._samples.put_nowait(sample)
