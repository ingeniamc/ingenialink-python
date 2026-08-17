"""Telemetry engine integration for VirtualDrive tests.

The adaptive telemetry engine is exposed through the ``telemetry`` PyO3 module.
VirtualDrive remains
responsible for register ownership and transport; this module supplies the
mapped register bytes to the engine and exposes its queued frames through the
TEL_* registers.
"""

import time
from threading import Event, Thread
from typing import TYPE_CHECKING, Callable, Optional

from telemetry import TelemetryEngine
from virtual_drive.register_service.modules import BaseModule
from virtual_drive.register_service.modules.capture.base import VirtualMonitoringMappedRegister
from virtual_drive.register_service.virtual_register import VirtualRegister

from ingenialink.enums.register import RegDtype
from ingenialink.utils._utils import convert_dtype_to_bytes

if TYPE_CHECKING:
    from virtual_drive.core import VirtualDrive
    from virtual_drive.register_service.register_value import RegisterValue
    from virtual_drive.register_service.service import RegisterService

    from ingenialink.dictionary import Dictionary
    from ingenialink.register import Register


class TelemetryModule(BaseModule):
    """Expose the telemetry engine through VirtualDrive registers.

    Args:
        dictionary: Dictionary used by the virtual drive.
        register_service: Register service owning the broker and address maps.
        max_channels: Number of ``TEL_CFG_REG{n}_MAP`` registers to expose.
    """

    STATUS_REGISTER = "TEL_STATUS"
    DATA_REGISTER = "TEL_DATA_VALUE"
    SAMPLE_SIZE_REGISTER = "TEL_CFG_BYTES_VALUE"
    ENABLE_REGISTER = "TEL_ENABLE"
    FREQUENCY_DIVIDER_REGISTER = "TEL_FREQ_DIV"
    ADAPTIVE_RATE_REGISTER = "TEL_ADAPTIVE_RATE"
    MAPPED_REGISTER_COUNT_REGISTER = "TEL_CFG_TOTAL_MAP"
    MAPPED_REGISTER_PREFIX = "TEL_CFG_REG"

    BASE_FREQUENCY_HZ = 1_000_000
    TIMESTAMP_SIZE = 8
    FRAME_COUNT_SIZE = 2
    ENGINE_QUEUE_CAPACITY = 256
    MIN_PROCESS_INTERVAL_S = 0.00005
    REQUIRED_REGISTERS = (
        STATUS_REGISTER,
        ENABLE_REGISTER,
        FREQUENCY_DIVIDER_REGISTER,
        ADAPTIVE_RATE_REGISTER,
        MAPPED_REGISTER_COUNT_REGISTER,
        SAMPLE_SIZE_REGISTER,
        DATA_REGISTER,
    )

    def __init__(
        self,
        dictionary: "Dictionary",
        register_service: "RegisterService",
        max_channels: int = 2,
    ) -> None:
        super().__init__(dictionary)
        self._register_service = register_service
        self._broker = register_service._broker  # noqa: SLF001
        self._engine = TelemetryEngine(queue_capacity=self.ENGINE_QUEUE_CAPACITY)
        self._status = 0
        self._freq_divider = 1
        self._adaptive_rate = 0
        self._number_mapped = 0
        self._mapped_configs: dict[int, VirtualMonitoringMappedRegister] = {}
        self._channels_register: dict[int, Register] = {}
        self._channels_dtype: dict[int, RegDtype] = {}
        self._channels_size: dict[int, int] = {}
        self._sampler: Optional[Thread] = None
        self._stop_event = Event()
        self._start_monotonic_ns = 0
        self._define_registers(max_channels)

    def _define_registers(self, max_channels: int) -> None:
        missing_required_registers: list[str] = []
        simple_registers: list[
            tuple[str, Callable[[], RegisterValue], Optional[Callable[[RegisterValue], None]]]
        ] = [
            (self.STATUS_REGISTER, self._read_status, None),
            (self.ENABLE_REGISTER, self._read_enable, self._write_enable),
            (self.FREQUENCY_DIVIDER_REGISTER, self._read_freq_divider, self._write_freq_divider),
            (self.ADAPTIVE_RATE_REGISTER, self._read_adaptive_rate, self._write_adaptive_rate),
            (
                self.MAPPED_REGISTER_COUNT_REGISTER,
                self._read_number_mapped,
                self._write_number_mapped,
            ),
            (self.SAMPLE_SIZE_REGISTER, self._read_sample_size, None),
            (self.DATA_REGISTER, self._read_data, None),
        ]
        for register_id, reader, writer in simple_registers:
            register = self._get_register(0, register_id)
            if register is None:
                missing_required_registers.append(register_id)
                continue
            self.add_owned_register(VirtualRegister(register, reader, writer))

        for channel in range(max_channels):
            register_id = f"{self.MAPPED_REGISTER_PREFIX}{channel}_MAP"
            register = self._get_register(0, register_id)
            if register is None:
                continue
            mapped_register = VirtualMonitoringMappedRegister(register)
            self.add_owned_register(mapped_register)
            self._mapped_configs[channel] = mapped_register

        if not missing_required_registers:
            self.enabled = True

    def _read_status(self) -> int:
        return self._status

    def _read_enable(self) -> int:
        return self._status & 1

    def _write_enable(self, value: "RegisterValue") -> None:
        if value:
            self._enable()
        else:
            self._disable()

    def _read_freq_divider(self) -> int:
        return self._freq_divider

    def _write_freq_divider(self, value: "RegisterValue") -> None:
        self._freq_divider = int(value)

    def _read_adaptive_rate(self) -> int:
        return self._adaptive_rate

    def _write_adaptive_rate(self, value: "RegisterValue") -> None:
        self._adaptive_rate = int(bool(value))

    def _read_number_mapped(self) -> int:
        return self._number_mapped

    def _write_number_mapped(self, value: "RegisterValue") -> None:
        self._number_mapped = int(value)

    def _read_sample_size(self) -> int:
        return self.TIMESTAMP_SIZE + self._engine.sample_size

    def _read_data(self) -> bytes:
        if not self._status & 1:
            return (0).to_bytes(self.FRAME_COUNT_SIZE, "little")

        frames: list[tuple[int, bytes]] = []
        while True:
            frame = self._engine.read_frame()
            if frame is None:
                break
            frames.append(frame)

        data = bytearray(len(frames).to_bytes(self.FRAME_COUNT_SIZE, "little"))
        for timestamp_tick, payload in frames:
            data.extend(timestamp_tick.to_bytes(self.TIMESTAMP_SIZE, "little"))
            data.extend(payload)
        return bytes(data)

    def _map_registers(self) -> None:
        self._channels_register.clear()
        self._channels_dtype.clear()
        self._channels_size.clear()
        for channel in range(self._number_mapped):
            mapped_register = self._mapped_configs.get(channel)
            if mapped_register is None:
                continue
            register = self._register_service.get_register_by_address(
                mapped_register.axis, mapped_register.address
            )
            self._channels_register[channel] = register
            self._channels_dtype[channel] = RegDtype(mapped_register.dtype)
            self._channels_size[channel] = mapped_register.size

    def _channel_value(self, channel: int) -> bytes:
        register = self._channels_register[channel]
        dtype = self._channels_dtype[channel]
        size = self._channels_size[channel]
        try:
            value = self._broker.read(register)
        except (KeyError, ValueError, PermissionError):
            value = 0
        if dtype != RegDtype.FLOAT:
            value = int(value)
        sample_bytes = convert_dtype_to_bytes(value, dtype)
        return (sample_bytes + b"\x00" * size)[:size]

    def _configure_engine_channels(self) -> None:
        for channel in range(self.ENGINE_QUEUE_CAPACITY):
            if channel >= 16:
                break
            self._engine.clear_channel(channel)
        for channel in sorted(self._channels_register):
            self._engine.set_channel(
                channel,
                channel + 1,
                self._channel_value(channel),
            )

    def _enable(self) -> None:
        if self._status & 1:
            return
        self._map_registers()
        self._configure_engine_channels()
        self._engine.set_adaptive_rate(bool(self._adaptive_rate))
        self._start_monotonic_ns = time.monotonic_ns()
        self._engine.start(self.BASE_FREQUENCY_HZ, self._freq_divider, 0)
        self._status |= 1
        self._stop_event.clear()
        self._sampler = Thread(target=self._sample_loop, daemon=True)
        self._sampler.start()

    def _disable(self) -> None:
        if not self._status & 1:
            return
        self._status &= ~1
        self._stop_event.set()
        self._engine.stop()
        if self._sampler is not None:
            self._sampler.join(timeout=1.0)
            self._sampler = None

    def _current_tick(self) -> int:
        elapsed_ns = time.monotonic_ns() - self._start_monotonic_ns
        return elapsed_ns * self.BASE_FREQUENCY_HZ // 1_000_000_000

    def _sample_loop(self) -> None:
        while not self._stop_event.is_set():
            for channel in self._channels_register:
                self._engine.update_channel_value(channel, self._channel_value(channel))
            self._engine.process(self._current_tick())
            effective_interval = self._engine.prescaler / self.BASE_FREQUENCY_HZ
            # The floor prevents a busy loop for high requested rates while the
            # engine still receives ticks often enough to honor its divider.
            self._stop_event.wait(max(self.MIN_PROCESS_INTERVAL_S, effective_interval))


def install_telemetry_module(
    server: "VirtualDrive", max_channels: int = 2
) -> Optional[TelemetryModule]:
    """Install the telemetry module when the dictionary supports it.

    Args:
        server: Virtual drive that will host the telemetry module.
        max_channels: Maximum number of telemetry mapping channels to expose.

    Returns:
        The installed module, or ``None`` if the dictionary lacks the required
        TEL_* registers.
    """
    register_service = server.register_service
    dictionary = register_service._dictionary  # noqa: SLF001
    if not all(
        register_id in dictionary.registers(0) for register_id in TelemetryModule.REQUIRED_REGISTERS
    ):
        return None
    module = TelemetryModule(dictionary, register_service, max_channels=max_channels)
    return register_service.register_module(module)
