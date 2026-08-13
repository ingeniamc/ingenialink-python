import json
import logging
import time
from contextlib import suppress
from threading import Event

import pyarrow.parquet as pq
import pytest

from ingenialink.enums.register import RegDtype
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.ethercat.telemetry import (
    ETHERCAT_TELEMETRY,
    EthercatTelemetry,
    TelemetryDescriptor,
    TelemetryFrame,
    TelemetryPoller,
    TelemetryRecorder,
    TelemetrySample,
)
from ingenialink.exceptions import ILRegisterAccessError
from ingenialink.register import Register
from ingenialink.virtual.ethercat.servo import VirtualEthercatServo
from ingenialink.virtual.ethernet.servo import VirtualEthernetServo

logger = logging.getLogger(__name__)


def _skip_virtual_generator_test(servo) -> None:
    """Skip generator waveform tests when only the generic virtual drive is available."""
    if isinstance(servo, (VirtualEthercatServo, VirtualEthernetServo)):
        pytest.skip("The virtual drive does not simulate the internal feedback generator")


def _get_telemetry_test_register(servo):
    """Get the production telemetry register or the dedicated virtual test register.

    Returns:
        Register used as the telemetry source for the current servo.
    """
    if isinstance(servo, VirtualEthercatServo):
        return servo.dictionary.get_register("TEST_TELEMETRY_U16", axis=0)
    return servo.dictionary.get_register("DRV_PROT_VBUS_VALUE", axis=1)


@pytest.mark.ethercat
def test_telemetry_configures_and_reads_frames(telemetry_servo) -> None:
    """Verify that an EtherCAT drive produces raw telemetry frames."""
    telemetry = EthercatTelemetry(telemetry_servo)
    register = _get_telemetry_test_register(telemetry_servo)
    actual_frequency = telemetry.configure([register], desired_frequency=10_000)
    assert actual_frequency == 10_000

    try:
        telemetry.start()
        assert telemetry.is_running()
        deadline = time.monotonic() + 2.0
        frame = None
        while time.monotonic() < deadline:
            if telemetry.sample_size() > 0:
                try:
                    frame = telemetry.read_frame()
                    break
                except ILRegisterAccessError:
                    pass
            time.sleep(0.01)
        assert frame is not None
        assert len(frame.data) == telemetry.sample_size()
    finally:
        telemetry.stop()


@pytest.mark.ethercat
def test_telemetry_firmware_timestamps_are_incremental(telemetry_servo) -> None:
    """Verify that firmware telemetry timestamps increase in arrival order."""
    telemetry = EthercatTelemetry(telemetry_servo)
    register = _get_telemetry_test_register(telemetry_servo)
    telemetry.configure([register], desired_frequency=2_000)
    timestamps: list[int] = []

    try:
        telemetry.start()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and len(timestamps) < 100:
            with suppress(ILRegisterAccessError):
                timestamps.extend(frame.timestamp_tick for frame in telemetry.read_frames())
            if len(timestamps) < 100:
                time.sleep(0.01)

        assert len(timestamps) >= 100
        inversion = next(
            (
                (previous, current)
                for previous, current in zip(timestamps, timestamps[1:])
                if current <= previous
            ),
            None,
        )
        assert inversion is None, f"Non-incremental firmware timestamps: {inversion}"
    finally:
        telemetry.stop()


RECORDING_DURATION_S = 10.0
COMPLETE_ACCESS_BUFFER_SIZES = (1_024, 2_048, 4_096, 8_192, 16_384, 32_768)


@pytest.mark.ethercat
def test_telemetry_complete_access_buffer_size_sweep(telemetry_servo) -> None:
    """Find the largest complete-access buffer accepted by the drive."""
    telemetry = EthercatTelemetry(telemetry_servo)
    register = _get_telemetry_test_register(telemetry_servo)
    telemetry.configure([register], desired_frequency=1_000)
    largest_supported_size = 0

    try:
        telemetry.start()
        time.sleep(0.05)
        for buffer_size in COMPLETE_ACCESS_BUFFER_SIZES:
            try:
                telemetry_servo.read_complete_access(
                    telemetry.descriptor.data_reg_uid,
                    subnode=0,
                    buffer_size=buffer_size,
                )
            except ILRegisterAccessError:
                break
            largest_supported_size = buffer_size
    finally:
        telemetry.stop()

    logger.info(
        "Largest supported telemetry complete-access buffer: %d bytes",
        largest_supported_size,
    )
    assert largest_supported_size >= COMPLETE_ACCESS_BUFFER_SIZES[0]


def _log_generator_registers(servo, context: str) -> None:
    logger.info(
        "Internal generator %s: mode=%s freq=%s gain=%s offset=%s cycles=%s value=%s",
        context,
        servo.read("FBK_GEN_MODE", subnode=1),
        servo.read("FBK_GEN_FREQ", subnode=1),
        servo.read("FBK_GEN_GAIN", subnode=1),
        servo.read("FBK_GEN_OFFSET", subnode=1),
        servo.read("FBK_GEN_CYCLES", subnode=1),
        servo.read("FBK_GEN_VALUE", subnode=1),
    )


def _record_generator_capture(
    servo,
    test_output_handler,
    mode_name: str,
    mode_value: int,
    generator_frequency_hz: float,
    telemetry_frequency_hz: float,
    adaptive_rate: bool,
) -> "pq.Table":
    """Configure the internal generator, record it to Parquet, and return the captured table.

    Restores the generator to Constant mode afterwards regardless of outcome.

    Returns:
        The recorded table, with the generator, bus voltage, and phase current columns.
    """
    servo.write("DRV_OP_CMD", 0, subnode=1)
    servo.write("COMMU_ANGLE_SENSOR", 3, subnode=1)
    servo.write("COMMU_PHASING_MODE", 2, subnode=1)
    servo.write("FBK_GEN_MODE", mode_value, subnode=1)
    servo.write("FBK_GEN_FREQ", generator_frequency_hz, subnode=1)
    servo.write("FBK_GEN_GAIN", 1.0, subnode=1)
    servo.write("FBK_GEN_OFFSET", 0.0, subnode=1)
    # Far more cycles than fit in the capture window, so the waveform is still running when
    # recording stops regardless of what a cycle count of 0 would mean.
    servo.write(
        "FBK_GEN_CYCLES",
        round(generator_frequency_hz * RECORDING_DURATION_S * 10),
        subnode=1,
    )
    servo.write("FBK_GEN_REARM", 1, subnode=1)
    _log_generator_registers(servo, "after configuration")

    registers = [
        servo.dictionary.get_register("FBK_GEN_VALUE", axis=1),
        servo.dictionary.get_register("DRV_PROT_VBUS_VALUE", axis=1),
        servo.dictionary.get_register("FBK_CUR_A_VALUE", axis=1),
    ]
    output_dir = test_output_handler.tests_output_dir / "ethercat_telemetry"
    output_dir.mkdir(parents=True, exist_ok=True)
    rate_mode = "adaptive" if adaptive_rate else "fixed"
    filename = (
        f"{mode_name}_gen{generator_frequency_hz:g}hz_"
        f"tel{telemetry_frequency_hz:g}hz_{rate_mode}.parquet"
    )
    path = output_dir / filename

    try:
        with TelemetryRecorder(
            servo,
            registers,
            path,
            frequency=telemetry_frequency_hz,
            adaptive_rate=adaptive_rate,
        ) as recorder:
            assert recorder.is_recording
            deadline = time.monotonic() + RECORDING_DURATION_S
            next_log = time.monotonic()
            while time.monotonic() < deadline:
                now = time.monotonic()
                if now >= next_log:
                    _log_generator_registers(servo, "during recording")
                    next_log += 1.0
                time.sleep(min(0.1, max(0.0, deadline - now)))
    finally:
        _log_generator_registers(servo, "before disabling")
        servo.write("FBK_GEN_MODE", 0, subnode=1)
        _log_generator_registers(servo, "after disabling")

    table = pq.read_table(path)
    assert table.num_rows > 0
    assert table.column_names == [
        "timestamp",
        "host_time",
        "FBK_GEN_VALUE",
        "DRV_PROT_VBUS_VALUE",
        "FBK_CUR_A_VALUE",
    ]
    timestamps = table.column("timestamp").to_pylist()
    assert timestamps == sorted(timestamps)
    return table


@pytest.mark.ethercat
@pytest.mark.parametrize("adaptive_rate", [False, True], ids=["fixed", "adaptive"])
@pytest.mark.parametrize("telemetry_frequency_hz", [1_000.0, 5_000.0, 20_000.0])
@pytest.mark.parametrize("generator_frequency_hz", [1.0, 5.0, 20.0])
def test_telemetry_recorder_captures_internal_generator_saw_tooth_signal(
    servo,
    test_output_handler,
    generator_frequency_hz: float,
    telemetry_frequency_hz: float,
    adaptive_rate: bool,
) -> None:
    """Verify TelemetryRecorder captures a saw-tooth waveform from the internal generator.

    The internal generator injects a synthetic waveform into the feedback path, so this
    exercises a real changing signal without commanding any motor motion. It is recorded
    alongside two other frequently-changing drive signals to demonstrate a multi-channel
    capture. Each generator/telemetry frequency pair is left as its own Parquet file under
    the test output directory for inspection and comparison.
    """
    _skip_virtual_generator_test(servo)
    table = _record_generator_capture(
        servo,
        test_output_handler,
        "saw_tooth",
        1,
        generator_frequency_hz,
        telemetry_frequency_hz,
        adaptive_rate,
    )

    generator_samples = table.column("FBK_GEN_VALUE").to_pylist()
    deltas = [
        current - previous for previous, current in zip(generator_samples, generator_samples[1:])
    ]
    assert any(delta > 0 for delta in deltas), "Saw-tooth capture should show a rising ramp"
    assert any(delta < 0 for delta in deltas), "Saw-tooth capture should show a reset"


@pytest.mark.ethercat
@pytest.mark.parametrize("adaptive_rate", [False, True], ids=["fixed", "adaptive"])
@pytest.mark.parametrize("telemetry_frequency_hz", [1_000.0, 5_000.0, 20_000.0])
@pytest.mark.parametrize("generator_frequency_hz", [1.0, 5.0, 20.0])
def test_telemetry_recorder_captures_internal_generator_square_signal(
    servo,
    test_output_handler,
    generator_frequency_hz: float,
    telemetry_frequency_hz: float,
    adaptive_rate: bool,
) -> None:
    """Verify TelemetryRecorder captures a square waveform from the internal generator.

    Same setup as the saw-tooth capture, but with the generator in Square mode, to show a
    different signal shape landing in the same Parquet schema.
    """
    _skip_virtual_generator_test(servo)
    table = _record_generator_capture(
        servo,
        test_output_handler,
        "square",
        2,
        generator_frequency_hz,
        telemetry_frequency_hz,
        adaptive_rate,
    )

    generator_samples = table.column("FBK_GEN_VALUE").to_pylist()
    deltas = [
        current - previous for previous, current in zip(generator_samples, generator_samples[1:])
    ]
    assert any(delta > 0 for delta in deltas), "Square capture should show a rising edge"
    assert any(delta < 0 for delta in deltas), "Square capture should show a falling edge"


def test_telemetry_reads_count_prefixed_frames(mocker) -> None:
    """Verify that the telemetry response declares its complete frame count."""
    servo = mocker.MagicMock(spec=EthercatServo)
    telemetry = EthercatTelemetry(servo)
    telemetry._frame_size = 12
    telemetry._read_buffer_size = 1024
    servo.read_complete_access.return_value = (
        (1).to_bytes(ETHERCAT_TELEMETRY.frame_count_size, "little")
        + (123).to_bytes(8, "little")
        + b"data"
        + b"tail"
    )

    frames = telemetry.read_frames()

    assert frames == [TelemetryFrame(data=b"data", timestamp_tick=123)]


def test_telemetry_read_uses_complete_access_so_gil_release_config_applies(mocker) -> None:
    """Verify telemetry reads go through the GIL-aware complete-access path.

    ``EthercatServo.read_complete_access`` forwards to ``_read_raw``, which is where
    ``GilReleaseConfig.sdo_read_write`` reaches ``pysoem.sdo_read``. Telemetry must use
    that path rather than bypassing it, or the ``release_gil`` guidance documented on
    ``TelemetryRecorder`` would have no effect.
    """
    servo = mocker.MagicMock(spec=EthercatServo)
    telemetry = EthercatTelemetry(servo)
    telemetry._frame_size = 12
    telemetry._read_buffer_size = 1024
    servo.read_complete_access.return_value = (0).to_bytes(
        ETHERCAT_TELEMETRY.frame_count_size, "little"
    )

    telemetry.read_frames()

    servo.read_complete_access.assert_called_once_with(
        ETHERCAT_TELEMETRY.data_reg_uid, subnode=0, buffer_size=1024
    )


@pytest.mark.parametrize(
    ("frequency", "expected_divider"),
    [
        (20, 50_000),
        (2_000, 500),
        (10_000, 100),
        (1_000_000, 1),
    ],
)
def test_telemetry_supports_multiple_sampling_frequencies(
    frequency: int, expected_divider: int
) -> None:
    """Verify sampling frequencies map to the expected firmware dividers."""
    assert EthercatTelemetry._frequency_to_divider(frequency) == expected_divider
    assert EthercatTelemetry._divider_to_frequency(expected_divider) == frequency


@pytest.mark.parametrize("adaptive_rate", [False, True])
def test_telemetry_configures_adaptive_rate(mocker, adaptive_rate: bool) -> None:
    """Verify both adaptive sampling modes are explicitly configured on the drive."""
    servo = mocker.MagicMock(spec=EthercatServo)
    register = _fake_register(mocker, "REG", RegDtype.U16)
    register.monitoring = mocker.MagicMock(subnode=0, address=1)
    telemetry = EthercatTelemetry(servo)

    telemetry.configure([register], adaptive_rate=adaptive_rate)

    servo.write.assert_any_call(
        ETHERCAT_TELEMETRY.adaptive_rate_reg_uid, int(adaptive_rate), subnode=0
    )


def test_telemetry_uses_descriptor_configuration(mocker) -> None:
    """Verify register UIDs and protocol limits come from the descriptor."""
    descriptor = TelemetryDescriptor(
        name="Test",
        max_channels=1,
        data_buffer_size=16,
        base_frequency_hz=1_000,
        max_frequency_divider=10,
        timestamp_size=4,
        timestamp_frequency_hz=1_000,
        frame_count_size=1,
        status_reg_uid="STATUS",
        data_reg_uid="DATA",
        sample_size_reg_uid="SAMPLE_SIZE",
        enable_reg_uid="ENABLE",
        frequency_divider_reg_uid="FREQUENCY",
        adaptive_rate_reg_uid="ADAPTIVE",
        mapped_register_count_reg_uid="MAP_COUNT",
        mapped_register_prefix="MAP_",
    )
    servo = mocker.MagicMock(spec=EthercatServo)
    register = _fake_register(mocker, "REG", RegDtype.U16)
    register.monitoring = mocker.MagicMock(subnode=0, address=1)
    telemetry = EthercatTelemetry(servo, descriptor)

    assert telemetry.configure([register], desired_frequency=500) == 500
    assert telemetry.descriptor is descriptor
    servo.write.assert_any_call("MAP_0_MAP", mocker.ANY, subnode=0)
    servo.write.assert_any_call("MAP_COUNT", 1, subnode=0)
    servo.write.assert_any_call("FREQUENCY", 2, subnode=0)
    servo.write.assert_any_call("ADAPTIVE", 0, subnode=0)


def test_telemetry_poller_decodes_multiple_registers_from_one_frame(mocker) -> None:
    """Verify that one frame decodes multiple mixed-width register values."""
    telemetry = mocker.MagicMock(spec=EthercatTelemetry)
    telemetry.descriptor = ETHERCAT_TELEMETRY
    first_register = mocker.MagicMock(spec=Register)
    first_register.dtype = RegDtype.U16
    first_register.identifier = "FIRST_REGISTER"
    first_register.bytes_to_value.side_effect = lambda data: int.from_bytes(data, "little")
    second_register = mocker.MagicMock(spec=Register)
    second_register.dtype = RegDtype.U32
    second_register.identifier = "SECOND_REGISTER"
    second_register.bytes_to_value.side_effect = lambda data: int.from_bytes(data, "little")
    third_register = mocker.MagicMock(spec=Register)
    third_register.dtype = RegDtype.U8
    third_register.identifier = "THIRD_REGISTER"
    third_register.bytes_to_value.side_effect = lambda data: int.from_bytes(data, "little")
    frame = TelemetryFrame(
        data=(123).to_bytes(2, "little") + (456).to_bytes(4, "little") + (7).to_bytes(1, "little"),
        timestamp_tick=2_000,
    )
    telemetry.read_frames.side_effect = [[frame], *([[]] * 1_000)]
    poller = TelemetryPoller(
        telemetry, [first_register, second_register, third_register], poll_interval=0.001
    )

    poller.start()
    try:
        _wait_for(lambda: poller.sample_count >= 1)
    finally:
        poller.stop()

    assert not poller.is_alive()
    assert poller.sample_count == 1
    assert poller.get_sample() == TelemetrySample(
        timestamp=0.002,
        values=(123, 456, 7),
    )


def _wait_for(condition, timeout: float = 1.0) -> None:
    """Block until ``condition()`` is true or ``timeout`` seconds have elapsed."""
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.001)


def test_telemetry_poller_reader_drains_repeatedly_until_empty(mocker) -> None:
    """Verify the reader keeps reading while frames are available, without waiting."""
    telemetry = mocker.MagicMock(spec=EthercatTelemetry)
    telemetry.descriptor = ETHERCAT_TELEMETRY
    register = _fake_register(mocker, "REG", RegDtype.U8)
    register.bytes_to_value.side_effect = lambda data: int.from_bytes(data, "little")
    frame = TelemetryFrame(data=b"\x01", timestamp_tick=1)
    remaining_non_empty_reads = 5
    read_calls: list[float] = []

    def read_frames() -> list[TelemetryFrame]:
        nonlocal remaining_non_empty_reads
        read_calls.append(time.monotonic())
        if remaining_non_empty_reads > 0:
            remaining_non_empty_reads -= 1
            return [frame]
        return []

    telemetry.read_frames.side_effect = read_frames
    poller = TelemetryPoller(telemetry, [register], poll_interval=0.5)

    start = time.monotonic()
    poller.start()
    try:
        _wait_for(lambda: len(read_calls) > 5, timeout=2.0)
        time.sleep(0.01)  # let the first empty read after the burst be observed
    finally:
        poller.stop()

    assert len(read_calls) >= 6
    # The five non-empty reads plus the following empty read all happen well before a
    # poll_interval wait would allow, proving the reader drains without pausing between
    # non-empty reads.
    assert read_calls[5] - start < 0.5
    assert poller.sample_count == 5


def test_telemetry_poller_decoder_runs_independently_of_reader(mocker) -> None:
    """Verify the decoder consumes queued frames even while the reader is stalled."""
    telemetry = mocker.MagicMock(spec=EthercatTelemetry)
    telemetry.descriptor = ETHERCAT_TELEMETRY
    register = _fake_register(mocker, "REG", RegDtype.U8)
    register.bytes_to_value.side_effect = lambda data: int.from_bytes(data, "little")
    reader_blocked = Event()
    telemetry.read_frames.side_effect = lambda: [] if reader_blocked.wait() else []
    poller = TelemetryPoller(telemetry, [register], poll_interval=0.01)

    poller.start()
    try:
        poller._raw_frames.append(TelemetryFrame(data=b"\x09", timestamp_tick=5))  # noqa: SLF001
        poller._frame_available.set()  # noqa: SLF001

        _wait_for(lambda: poller.sample_count >= 1)

        assert poller.sample_count == 1
        assert poller.get_sample() == TelemetrySample(timestamp=0.000005, values=(9,))
    finally:
        reader_blocked.set()
        poller.stop()


def test_telemetry_poller_reader_error_stops_decoder(mocker) -> None:
    """Verify a reader exception surfaces via error and stops the decoder too."""
    telemetry = mocker.MagicMock(spec=EthercatTelemetry)
    telemetry.descriptor = ETHERCAT_TELEMETRY
    register = _fake_register(mocker, "REG", RegDtype.U8)
    telemetry.read_frames.side_effect = RuntimeError("transport failed")
    poller = TelemetryPoller(telemetry, [register], poll_interval=0.001)

    poller.start()
    poller._reader_thread.join(timeout=1.0)  # noqa: SLF001
    poller._decoder_thread.join(timeout=1.0)  # noqa: SLF001

    assert not poller.is_alive()
    assert isinstance(poller.error, RuntimeError)


def test_telemetry_poller_decoder_error_stops_reader(mocker) -> None:
    """Verify a decode error (frame size mismatch) surfaces via error and stops the reader."""
    telemetry = mocker.MagicMock(spec=EthercatTelemetry)
    telemetry.descriptor = ETHERCAT_TELEMETRY
    register = _fake_register(mocker, "REG", RegDtype.U16)
    bad_frame = TelemetryFrame(data=b"\x01", timestamp_tick=1)  # 1 byte, but U16 needs 2
    telemetry.read_frames.side_effect = [[bad_frame], *([[]] * 1_000)]
    poller = TelemetryPoller(telemetry, [register], poll_interval=0.001)

    poller.start()
    poller._decoder_thread.join(timeout=1.0)  # noqa: SLF001
    poller._reader_thread.join(timeout=1.0)  # noqa: SLF001

    assert not poller.is_alive()
    assert isinstance(poller.error, RuntimeError)


def test_telemetry_poller_retries_after_transient_register_access_error(mocker) -> None:
    """Verify a transient ILRegisterAccessError is retried after poll_interval."""
    telemetry = mocker.MagicMock(spec=EthercatTelemetry)
    telemetry.descriptor = ETHERCAT_TELEMETRY
    register = _fake_register(mocker, "REG", RegDtype.U8)
    register.bytes_to_value.side_effect = lambda data: int.from_bytes(data, "little")
    frame = TelemetryFrame(data=b"\x01", timestamp_tick=1)
    transient_error = ILRegisterAccessError(
        base_message="transient",
        reg=mocker.MagicMock(),
        base_exception=Exception("transient"),
        reason="transient",
    )
    telemetry.read_frames.side_effect = [
        transient_error,
        [frame],
        *([[]] * 1_000),
    ]
    poller = TelemetryPoller(telemetry, [register], poll_interval=0.01)

    poller.start()
    try:
        _wait_for(lambda: poller.sample_count >= 1)
    finally:
        poller.stop()

    assert poller.sample_count == 1
    assert poller.error is None


def test_telemetry_poller_stop_joins_worker_threads_without_deadlock(mocker) -> None:
    """Verify stop() joins both threads promptly, even with a pending backlog."""
    telemetry = mocker.MagicMock(spec=EthercatTelemetry)
    telemetry.descriptor = ETHERCAT_TELEMETRY
    register = _fake_register(mocker, "REG", RegDtype.U8)
    register.bytes_to_value.side_effect = lambda data: int.from_bytes(data, "little")
    frame = TelemetryFrame(data=b"\x01", timestamp_tick=1)
    frames_remaining = 5_000

    def read_frames() -> list[TelemetryFrame]:
        nonlocal frames_remaining
        if frames_remaining <= 0:
            return []
        batch = min(50, frames_remaining)
        frames_remaining -= batch
        return [frame] * batch

    telemetry.read_frames.side_effect = read_frames
    poller = TelemetryPoller(telemetry, [register], poll_interval=0.01)

    poller.start()
    start = time.monotonic()
    poller.stop()
    elapsed = time.monotonic() - start

    assert not poller.is_alive()
    assert elapsed < 2.0

    poller.stop()  # idempotent: must not hang or raise


def _fake_register(mocker, identifier: str, dtype: RegDtype) -> Register:
    register = mocker.MagicMock(spec=Register)
    register.identifier = identifier
    register.dtype = dtype
    return register


def _queue_samples(poller: TelemetryPoller, samples: list[TelemetrySample]) -> None:
    """Make a mocked poller's ``get_sample`` return ``samples`` then ``None`` forever."""
    remaining = list(samples)
    poller.get_sample.side_effect = lambda: remaining.pop(0) if remaining else None
    poller.error = None


@pytest.mark.parametrize("adaptive_rate", [False, True])
def test_telemetry_recorder_writes_samples_to_parquet(
    tmp_path, mocker, adaptive_rate: bool
) -> None:
    """Verify that recorded samples land in the Parquet file as separate columns."""
    servo = mocker.MagicMock(spec=EthercatServo)
    register = _fake_register(mocker, "REG", RegDtype.FLOAT)
    telemetry = mocker.patch("ingenialink.ethercat.telemetry.EthercatTelemetry").return_value
    telemetry.configure.return_value = 1_000
    poller = mocker.patch("ingenialink.ethercat.telemetry.TelemetryPoller").return_value
    _queue_samples(
        poller,
        [
            TelemetrySample(timestamp=0.0, values=(1.0,)),
            TelemetrySample(timestamp=0.001, values=(2.0,)),
        ],
    )
    path = tmp_path / "telemetry.parquet"

    recorder = TelemetryRecorder(
        servo, [register], path, batch_size=10, adaptive_rate=adaptive_rate
    )
    recorder.start()
    recorder.stop()

    telemetry.configure.assert_called_once_with(
        (register,), desired_frequency=1_000, adaptive_rate=adaptive_rate
    )
    rows = pq.read_table(path).to_pylist()
    assert [{"timestamp": row["timestamp"], "REG": row["REG"]} for row in rows] == [
        {"timestamp": 0.0, "REG": 1.0},
        {"timestamp": 0.001, "REG": 2.0},
    ]
    assert rows[0]["host_time"] is not None
    assert rows[1]["host_time"] is None


def test_telemetry_recorder_add_marker_writes_metadata(tmp_path, mocker) -> None:
    """Verify markers land in the file's metadata as a JSON list, keyed by column time."""
    servo = mocker.MagicMock(spec=EthercatServo)
    register = _fake_register(mocker, "REG", RegDtype.FLOAT)
    mocker.patch("ingenialink.ethercat.telemetry.EthercatTelemetry").return_value
    poller = mocker.patch("ingenialink.ethercat.telemetry.TelemetryPoller").return_value
    _queue_samples(
        poller,
        [
            TelemetrySample(timestamp=0.0, values=(1.0,)),
            TelemetrySample(timestamp=0.001, values=(2.0,)),
        ],
    )
    path = tmp_path / "telemetry.parquet"

    recorder = TelemetryRecorder(servo, [register], path, batch_size=10)
    recorder.start()
    recorder.add_marker("start of test")
    recorder.add_marker("explicit time", timestamp=0.0005)
    recorder.stop()

    metadata = pq.ParquetFile(path).metadata.metadata
    markers = json.loads(metadata[TelemetryRecorder.METADATA_MARKERS_KEY.encode()])
    assert markers == [
        {"time": 0.001, "label": "start of test"},
        {"time": 0.0005, "label": "explicit time"},
    ]


def test_telemetry_recorder_add_marker_before_start_raises(tmp_path, mocker) -> None:
    """Verify adding a marker before recording starts raises."""
    servo = mocker.MagicMock(spec=EthercatServo)
    register = _fake_register(mocker, "REG", RegDtype.U8)
    recorder = TelemetryRecorder(servo, [register], tmp_path / "telemetry.parquet")

    with pytest.raises(RuntimeError):
        recorder.add_marker("too early")


def test_telemetry_recorder_add_marker_without_samples_requires_explicit_time(
    tmp_path, mocker
) -> None:
    """Verify a marker added before any sample is written needs an explicit timestamp."""
    servo = mocker.MagicMock(spec=EthercatServo)
    register = _fake_register(mocker, "REG", RegDtype.U8)
    mocker.patch("ingenialink.ethercat.telemetry.EthercatTelemetry").return_value
    poller = mocker.patch("ingenialink.ethercat.telemetry.TelemetryPoller").return_value
    _queue_samples(poller, [])
    recorder = TelemetryRecorder(servo, [register], tmp_path / "telemetry.parquet")
    recorder.start()

    with pytest.raises(RuntimeError):
        recorder.add_marker("no samples yet")

    recorder.add_marker("explicit", timestamp=1.5)
    recorder.stop()

    metadata = pq.ParquetFile(tmp_path / "telemetry.parquet").metadata.metadata
    markers = json.loads(metadata[TelemetryRecorder.METADATA_MARKERS_KEY.encode()])
    assert markers == [{"time": 1.5, "label": "explicit"}]


def test_telemetry_recorder_is_a_context_manager(tmp_path, mocker) -> None:
    """Verify entering and exiting the recorder starts and stops recording."""
    servo = mocker.MagicMock(spec=EthercatServo)
    register = _fake_register(mocker, "REG", RegDtype.U16)
    poller = mocker.patch("ingenialink.ethercat.telemetry.TelemetryPoller").return_value
    _queue_samples(poller, [TelemetrySample(timestamp=0.0, values=(5,))])
    path = tmp_path / "telemetry.parquet"

    with TelemetryRecorder(servo, [register], path) as recorder:
        assert recorder.is_recording

    assert not recorder.is_recording
    rows = pq.read_table(path).to_pylist()
    assert [{"timestamp": row["timestamp"], "REG": row["REG"]} for row in rows] == [
        {"timestamp": 0.0, "REG": 5}
    ]


def test_telemetry_recorder_resume_appends_to_the_same_file(tmp_path, mocker) -> None:
    """Verify that pausing and starting again keeps the file open and appends."""
    servo = mocker.MagicMock(spec=EthercatServo)
    register = _fake_register(mocker, "REG", RegDtype.U8)
    telemetry = mocker.patch("ingenialink.ethercat.telemetry.EthercatTelemetry").return_value
    poller_cls = mocker.patch("ingenialink.ethercat.telemetry.TelemetryPoller")
    first_poller, second_poller = mocker.MagicMock(), mocker.MagicMock()
    poller_cls.side_effect = [first_poller, second_poller]
    _queue_samples(first_poller, [TelemetrySample(timestamp=0.0, values=(1,))])
    _queue_samples(second_poller, [TelemetrySample(timestamp=0.001, values=(2,))])
    path = tmp_path / "telemetry.parquet"

    recorder = TelemetryRecorder(servo, [register], path, batch_size=10)
    recorder.start()
    recorder.pause()
    recorder.start()
    recorder.stop()

    assert telemetry.configure.call_count == 1
    assert telemetry.start.call_count == 2
    assert telemetry.stop.call_count == 2
    rows = pq.read_table(path).to_pylist()
    assert [{"timestamp": row["timestamp"], "REG": row["REG"]} for row in rows] == [
        {"timestamp": 0.0, "REG": 1},
        {"timestamp": 0.001, "REG": 2},
    ]


def test_telemetry_recorder_pause_without_start_raises(tmp_path, mocker) -> None:
    """Verify pausing a recorder that never started raises."""
    servo = mocker.MagicMock(spec=EthercatServo)
    register = _fake_register(mocker, "REG", RegDtype.U8)
    recorder = TelemetryRecorder(servo, [register], tmp_path / "telemetry.parquet")

    with pytest.raises(RuntimeError):
        recorder.pause()


def test_telemetry_recorder_double_start_raises(tmp_path, mocker) -> None:
    """Verify starting an already-running recorder raises."""
    servo = mocker.MagicMock(spec=EthercatServo)
    register = _fake_register(mocker, "REG", RegDtype.U8)
    poller = mocker.patch("ingenialink.ethercat.telemetry.TelemetryPoller").return_value
    _queue_samples(poller, [])
    recorder = TelemetryRecorder(servo, [register], tmp_path / "telemetry.parquet")

    recorder.start()
    try:
        with pytest.raises(RuntimeError):
            recorder.start()
    finally:
        recorder.stop()


def test_telemetry_recorder_requires_pyarrow(mocker, tmp_path) -> None:
    """Verify a missing pyarrow dependency raises a clear ImportError."""
    servo = mocker.MagicMock(spec=EthercatServo)
    register = _fake_register(mocker, "REG", RegDtype.U8)
    mocker.patch.dict("sys.modules", {"pyarrow": None})

    with pytest.raises(ImportError, match="pyarrow"):
        TelemetryRecorder(servo, [register], tmp_path / "telemetry.parquet")


@pytest.mark.parametrize("adaptive_rate", [False, True])
def test_virtual_telemetry_configures_and_streams_frames(
    virtual_drive_ethercat_telemetry, adaptive_rate: bool
) -> None:
    """Verify telemetry sampling against a fake TEL_* firmware service."""
    _, _, servo = virtual_drive_ethercat_telemetry
    telemetry = EthercatTelemetry(servo)
    counter = servo.dictionary.get_register("DRV_DIAG_ERROR_LAST_COM", axis=0)
    test_channel = servo.dictionary.get_register("TEST_TELEMETRY_U16", axis=0)
    servo.write("TEST_TELEMETRY_U16", 4321, subnode=0)

    actual_frequency = telemetry.configure(
        [counter, test_channel], desired_frequency=5_000, adaptive_rate=adaptive_rate
    )
    assert actual_frequency == 5_000
    assert servo.read("TEL_ADAPTIVE_RATE", subnode=0) == int(adaptive_rate)
    assert telemetry.sample_size() == 0  # no mapping applied until telemetry is enabled

    try:
        telemetry.start()
        assert telemetry.is_running()

        deadline = time.monotonic() + 2.0
        frames: list[TelemetryFrame] = []
        while time.monotonic() < deadline and len(frames) < 20:
            with suppress(ILRegisterAccessError):
                frames.extend(telemetry.read_frames())
            if len(frames) < 20:
                time.sleep(0.01)

        assert len(frames) >= 20
        assert telemetry.sample_size() == 6  # s32 counter + u16 test channel

        for frame in frames:
            assert len(frame.data) == 6
            counter_value = int.from_bytes(frame.data[0:4], "little", signed=True)
            test_channel_value = int.from_bytes(frame.data[4:6], "little")
            assert counter_value == 0
            assert test_channel_value == 4321

        timestamps = [frame.timestamp_tick for frame in frames]
        inversion = next(
            (
                (previous, current)
                for previous, current in zip(timestamps, timestamps[1:])
                if current <= previous
            ),
            None,
        )
        assert inversion is None, f"Non-incremental firmware timestamps: {inversion}"
    finally:
        telemetry.stop()
        assert not telemetry.is_running()


def test_virtual_telemetry_recorder_writes_real_samples_to_parquet(
    virtual_drive_ethercat_telemetry, tmp_path
) -> None:
    """Verify TelemetryRecorder end-to-end against a fake TEL_* firmware service."""
    _, _, servo = virtual_drive_ethercat_telemetry
    counter = servo.dictionary.get_register("DRV_DIAG_ERROR_LAST_COM", axis=0)
    path = tmp_path / "telemetry.parquet"

    with TelemetryRecorder(servo, [counter], path, frequency=2_000, batch_size=10) as recorder:
        deadline = time.monotonic() + 2.0
        while recorder._poller is not None and recorder._poller.sample_count < 20:  # noqa: SLF001
            if time.monotonic() > deadline:
                break
            time.sleep(0.01)

    table = pq.read_table(path)
    assert table.num_rows >= 20
    assert table.column_names == ["timestamp", "host_time", "DRV_DIAG_ERROR_LAST_COM"]
    assert all(value == 0 for value in table.column("DRV_DIAG_ERROR_LAST_COM").to_pylist())
    timestamps = table.column("timestamp").to_pylist()
    assert timestamps == sorted(timestamps)


def test_virtual_telemetry_recorder_pause_and_resume(
    virtual_drive_ethercat_telemetry, tmp_path
) -> None:
    """Verify pause/start against a fake TEL_* firmware service resumes into the same file."""
    _, _, servo = virtual_drive_ethercat_telemetry
    counter = servo.dictionary.get_register("DRV_DIAG_ERROR_LAST_COM", axis=0)
    path = tmp_path / "telemetry.parquet"

    recorder = TelemetryRecorder(servo, [counter], path, frequency=2_000, batch_size=10)
    recorder.start()
    time.sleep(0.1)
    recorder.pause()
    assert not recorder.is_recording
    assert not recorder._telemetry.is_running()  # noqa: SLF001

    recorder.start()
    time.sleep(0.1)
    recorder.stop()

    table = pq.read_table(path)
    assert table.num_rows > 0
