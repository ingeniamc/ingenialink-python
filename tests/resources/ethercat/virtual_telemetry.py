"""Fake EtherCAT telemetry (TEL_*) service for VirtualDrive-backed tests.

virtual_drive does not implement the telemetry protocol used by
:class:`ingenialink.ethercat.telemetry.EthercatTelemetry`. This module plugs a
``TelemetryModule`` into a running :class:`virtual_drive.core.VirtualDrive`
through its public register-ownership API
(``RegisterService.register_module`` / ``RegisterBroker.register_virtual_register``),
so tests can exercise the real client against a fake but protocol-accurate
firmware instead of mocks.
"""

from threading import Event, Lock, Thread
from typing import TYPE_CHECKING, Callable, Optional

from virtual_drive.register_service.modules import BaseModule
from virtual_drive.register_service.modules.capture.base import VirtualMonitoringMappedRegister
from virtual_drive.register_service.virtual_register import VirtualRegister

from ingenialink.enums.register import RegDtype
from ingenialink.utils._utils import convert_dtype_to_bytes

if TYPE_CHECKING:
    from virtual_drive.register_service.broker import RegisterBroker
    from virtual_drive.register_service.register_value import RegisterValue
    from virtual_drive.register_service.service import RegisterService

    from ingenialink.dictionary import Dictionary
    from ingenialink.register import Register


class TelemetryModule(BaseModule):
    """Fake firmware implementation of the EtherCAT telemetry (TEL_*) registers.

    Mirrors :class:`ingenialink.ethercat.telemetry.EthercatTelemetry`: mapped
    channels are decoded from ``TEL_CFG_REG{n}_MAP`` the same way real
    firmware does, and enabled telemetry appends ``[8-byte tick][payload]``
    frames to a byte buffer drained on ``TEL_DATA_VALUE`` reads.

    Args:
        dictionary: Dictionary used by the virtual drive.
        register_service: Register service owning the broker and address maps.
        max_channels: Number of ``TEL_CFG_REG{n}_MAP`` registers to look for.

    """

    STATUS_REGISTER = "TEL_STATUS"
    DATA_REGISTER = "TEL_DATA_VALUE"
    SAMPLE_SIZE_REGISTER = "TEL_CFG_BYTES_VALUE"
    ENABLE_REGISTER = "TEL_ENABLE"
    FREQUENCY_DIVIDER_REGISTER = "TEL_FREQ_DIV"
    MAPPED_REGISTER_COUNT_REGISTER = "TEL_CFG_TOTAL_MAP"
    MAPPED_REGISTER_PREFIX = "TEL_CFG_REG"

    BASE_FREQUENCY_HZ = 1_000_000
    TIMESTAMP_SIZE = 8
    FRAME_COUNT_SIZE = 2

    def __init__(
        self,
        dictionary: "Dictionary",
        register_service: "RegisterService",
        max_channels: int = 2,
    ) -> None:
        super().__init__(dictionary)
        self._register_service = register_service
        self._broker: RegisterBroker = register_service._broker  # noqa: SLF001
        self._status = 0
        self._freq_divider = 1
        self._number_mapped = 0
        self._bytes_per_sample = 0
        self._tick = 0
        self._mapped_configs: dict[int, VirtualMonitoringMappedRegister] = {}
        self._channels_register: dict[int, Register] = {}
        self._channels_dtype: dict[int, RegDtype] = {}
        self._channels_size: dict[int, int] = {}
        self._buffer = bytearray()
        self._buffer_lock = Lock()
        self._sampler: Optional[Thread] = None
        self._stop_event = Event()
        self._define_registers(max_channels)

    def _define_registers(self, max_channels: int) -> None:
        missing_required_registers: list[str] = []
        simple_registers: list[
            tuple[str, Callable[[], RegisterValue], Optional[Callable[[RegisterValue], None]]]
        ] = [
            (self.STATUS_REGISTER, self._read_status, None),
            (self.ENABLE_REGISTER, self._read_enable, self._write_enable),
            (self.FREQUENCY_DIVIDER_REGISTER, self._read_freq_divider, self._write_freq_divider),
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

    def _read_number_mapped(self) -> int:
        return self._number_mapped

    def _write_number_mapped(self, value: "RegisterValue") -> None:
        self._number_mapped = int(value)

    def _read_sample_size(self) -> int:
        return self.TIMESTAMP_SIZE + self._bytes_per_sample

    def _read_data(self) -> bytes:
        frame_size = self.TIMESTAMP_SIZE + self._bytes_per_sample
        with self._buffer_lock:
            if frame_size <= 0:
                return self._pack_frame_count(0)
            frame_count = len(self._buffer) // frame_size
            used = frame_count * frame_size
            data = bytes(self._buffer[:used])
            del self._buffer[:used]
        return self._pack_frame_count(frame_count) + data

    @classmethod
    def _pack_frame_count(cls, frame_count: int) -> bytes:
        return frame_count.to_bytes(cls.FRAME_COUNT_SIZE, "little")

    def _map_registers(self) -> None:
        self._channels_register.clear()
        self._channels_dtype.clear()
        self._channels_size.clear()
        self._bytes_per_sample = 0
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
            self._bytes_per_sample += mapped_register.size

    def _enable(self) -> None:
        if self._status & 1:
            return
        self._map_registers()
        self._status |= 1
        self._stop_event.clear()
        self._sampler = Thread(target=self._sample_loop, daemon=True)
        self._sampler.start()

    def _disable(self) -> None:
        if not self._status & 1:
            return
        self._status &= ~1
        self._stop_event.set()
        if self._sampler is not None:
            self._sampler.join(timeout=1.0)
            self._sampler = None

    def _sample_loop(self) -> None:
        while not self._stop_event.is_set():
            self._sample_once()
            if self._freq_divider > 0:
                interval = self._freq_divider / self.BASE_FREQUENCY_HZ
            else:
                interval = 0.001
            self._stop_event.wait(interval)

    def _sample_once(self) -> None:
        if not self._channels_register:
            return
        frame = bytearray(self._tick.to_bytes(self.TIMESTAMP_SIZE, "little"))
        for channel in sorted(self._channels_register):
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
            if len(sample_bytes) < size:
                sample_bytes += b"\x00" * (size - len(sample_bytes))
            frame += sample_bytes
        with self._buffer_lock:
            self._buffer += frame
        self._tick += self._freq_divider


def install_telemetry_module(
    dictionary: "Dictionary", register_service: "RegisterService", max_channels: int = 2
) -> Optional[TelemetryModule]:
    """Wire a fake :class:`TelemetryModule` into a running virtual drive.

    Returns:
        The installed module, or ``None`` if the dictionary is missing any of
        the required ``TEL_*`` registers.

    """
    module = TelemetryModule(dictionary, register_service, max_channels=max_channels)
    return register_service.register_module(module)
