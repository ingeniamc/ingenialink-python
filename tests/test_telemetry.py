import logging
import time
from contextlib import suppress

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from ingenialink.enums.register import RegDtype
from ingenialink.ethercat.telemetry_descriptor import ETHERCAT_TELEMETRY
from ingenialink.exceptions import ILRegisterAccessError
from ingenialink.register import Register
from ingenialink.servo import Servo
from ingenialink.telemetry import Telemetry, TelemetryDescriptor, TelemetryReader, TelemetrySession
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


def _fake_register(mocker, identifier: str, dtype: RegDtype) -> Register:
    register = mocker.MagicMock(spec=Register)
    register.identifier = identifier
    register.dtype = dtype
    return register


class TestTelemetry:
    """Unit tests for ``Telemetry`` against a mocked servo."""

    def test_telemetry_reads_count_prefixed_frames(self, mocker) -> None:
        """Verify that raw telemetry reads preserve the complete-access response."""
        servo = mocker.MagicMock(spec=Servo)
        telemetry = Telemetry(servo, ETHERCAT_TELEMETRY)
        telemetry._frame_size = 12
        telemetry._read_buffer_size = 1024
        servo.read_complete_access.return_value = (
            (1).to_bytes(ETHERCAT_TELEMETRY.frame_count_size, "little")
            + (123).to_bytes(8, "little")
            + b"data"
            + b"tail"
        )

        access = telemetry.read_access()

        assert access == servo.read_complete_access.return_value

    def test_telemetry_requires_configuration_before_reading(self, mocker) -> None:
        """Verify reads and polling cannot start before telemetry is configured."""
        servo = mocker.MagicMock(spec=Servo)
        telemetry = Telemetry(servo, ETHERCAT_TELEMETRY)

        with pytest.raises(RuntimeError, match="configured"):
            telemetry.read_access()
        with pytest.raises(RuntimeError, match="configured"):
            telemetry.recommended_poll_interval()

    def test_telemetry_rejects_invalid_register_configuration(self, mocker) -> None:
        """Verify empty and unmapped register configurations fail early."""
        servo = mocker.MagicMock(spec=Servo)
        telemetry = Telemetry(servo, ETHERCAT_TELEMETRY)
        register = _fake_register(mocker, "REG", RegDtype.U16)
        register.monitoring = None

        with pytest.raises(ValueError, match="requires 1"):
            telemetry.configure([])
        with pytest.raises(RuntimeError, match="no telemetry mapping"):
            telemetry.configure([register])

    def test_telemetry_rejects_invalid_sample_size(self, mocker) -> None:
        """Verify firmware sizes smaller than the timestamp are rejected."""
        servo = mocker.MagicMock(spec=Servo)
        servo.read.return_value = ETHERCAT_TELEMETRY.timestamp_size - 1
        telemetry = Telemetry(servo, ETHERCAT_TELEMETRY)

        with pytest.raises(RuntimeError, match="smaller than its timestamp"):
            telemetry.sample_size()

    def test_telemetry_read_uses_complete_access_so_gil_release_config_applies(
        self, mocker
    ) -> None:
        """Verify telemetry reads go through the GIL-aware complete-access path.

        ``Servo.read_complete_access`` forwards to ``_read_raw``, which is where
        ``GilReleaseConfig.sdo_read_write`` reaches ``pysoem.sdo_read``. Telemetry must use
        that path rather than bypassing it, or the ``release_gil`` guidance documented on
        ``TelemetrySession`` would have no effect.
        """
        servo = mocker.MagicMock(spec=Servo)
        telemetry = Telemetry(servo, ETHERCAT_TELEMETRY)
        telemetry._frame_size = 12
        telemetry._read_buffer_size = 1024
        servo.read_complete_access.return_value = (0).to_bytes(
            ETHERCAT_TELEMETRY.frame_count_size, "little"
        )

        telemetry.read_access()

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
        self, frequency: int, expected_divider: int
    ) -> None:
        """Verify sampling frequencies map to the expected firmware dividers."""
        assert Telemetry._frequency_to_divider(frequency, ETHERCAT_TELEMETRY) == expected_divider
        assert (
            Telemetry._divider_to_frequency(expected_divider, ETHERCAT_TELEMETRY) == frequency
        )

    def test_telemetry_recommends_polling_at_half_buffer_capacity(self, mocker) -> None:
        """Calculate polling from the number of frames that fit in the read buffer."""
        servo = mocker.MagicMock(spec=Servo)
        registers = [
            _fake_register(mocker, "FIRST", RegDtype.U32),
            _fake_register(mocker, "SECOND", RegDtype.U32),
        ]
        for register in registers:
            register.monitoring = mocker.MagicMock(subnode=0, address=1)
        telemetry = Telemetry(servo, ETHERCAT_TELEMETRY)
        telemetry.configure(registers, desired_frequency=1_000)
        frame_size = ETHERCAT_TELEMETRY.timestamp_size + 8
        frames_per_read = (
            Telemetry._buffer_size_for(frame_size, ETHERCAT_TELEMETRY)
            - ETHERCAT_TELEMETRY.frame_count_size
        ) // frame_size

        assert telemetry.recommended_poll_interval() == pytest.approx(frames_per_read / 2 / 1_000)
        reader = TelemetryReader(telemetry, on_access=lambda _: None)
        assert reader.poll_interval == pytest.approx(frames_per_read / 2 / 1_000)

    @pytest.mark.parametrize("adaptive_rate", [False, True])
    def test_telemetry_configures_adaptive_rate(self, mocker, adaptive_rate: bool) -> None:
        """Verify both adaptive sampling modes are explicitly configured on the drive."""
        servo = mocker.MagicMock(spec=Servo)
        register = _fake_register(mocker, "REG", RegDtype.U16)
        register.monitoring = mocker.MagicMock(subnode=0, address=1)
        telemetry = Telemetry(servo, ETHERCAT_TELEMETRY)

        telemetry.configure([register], adaptive_rate=adaptive_rate)

        servo.write.assert_any_call(
            ETHERCAT_TELEMETRY.adaptive_rate_reg_uid, int(adaptive_rate), subnode=0
        )

    def test_telemetry_uses_descriptor_configuration(self, mocker) -> None:
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
        servo = mocker.MagicMock(spec=Servo)
        register = _fake_register(mocker, "REG", RegDtype.U16)
        register.monitoring = mocker.MagicMock(subnode=0, address=1)
        telemetry = Telemetry(servo, descriptor)

        assert telemetry.configure([register], desired_frequency=500, adaptive_rate=False) == 500
        assert telemetry.descriptor is descriptor
        servo.write.assert_any_call("MAP_0_MAP", mocker.ANY, subnode=0)
        servo.write.assert_any_call("MAP_COUNT", 1, subnode=0)
        servo.write.assert_any_call("FREQUENCY", 2, subnode=0)
        servo.write.assert_any_call("ADAPTIVE", 0, subnode=0)


class TestTelemetryReader:
    """Unit tests for ``TelemetryReader`` against a mocked ``Telemetry``."""

    def test_telemetry_reader_validates_constructor_arguments(self, mocker) -> None:
        """Verify the reader rejects invalid intervals and missing consumers."""
        telemetry = mocker.MagicMock(spec=Telemetry)

        with pytest.raises(ValueError, match="positive"):
            TelemetryReader(telemetry, poll_interval=0, on_access=lambda _: None)
        with pytest.raises(ValueError, match="callback"):
            TelemetryReader(telemetry, poll_interval=0.1)

    def test_telemetry_reader_ignores_transient_register_errors(self, mocker) -> None:
        """Verify transient servo access errors do not terminate the reader."""
        telemetry = mocker.MagicMock(spec=Telemetry)
        telemetry.descriptor = ETHERCAT_TELEMETRY
        access = (1).to_bytes(ETHERCAT_TELEMETRY.frame_count_size, "little") + b"payload"
        reads = iter([
            ILRegisterAccessError(
                base_message="read failed",
                reg=mocker.MagicMock(spec=Register),
                base_exception=Exception("busy"),
                reason="busy",
            ),
            access,
        ])

        def read_access() -> bytes:
            result = next(reads, b"\x00\x00")
            if isinstance(result, BaseException):
                raise result
            return result

        telemetry.read_access.side_effect = read_access
        accesses: list[bytes] = []
        reader = TelemetryReader(telemetry, poll_interval=0.001, on_access=accesses.append)

        reader.start()
        deadline = time.monotonic() + 1.0
        while not accesses and time.monotonic() < deadline:
            time.sleep(0.001)
        reader.stop()

        assert accesses == [access]
        assert reader.error is None

    def test_telemetry_reader_forwards_non_empty_accesses(self, mocker) -> None:
        """Verify the reader forwards complete accesses without decoding them in Python."""
        telemetry = mocker.MagicMock(spec=Telemetry)
        telemetry.descriptor = ETHERCAT_TELEMETRY
        access = (1).to_bytes(ETHERCAT_TELEMETRY.frame_count_size, "little") + b"payload"
        accesses: list[bytes] = []
        reads = iter([access, b"\x00\x00"])

        def read_access() -> bytes:
            return next(reads, b"\x00\x00")

        telemetry.read_access.side_effect = read_access
        reader = TelemetryReader(telemetry, poll_interval=0.001, on_access=accesses.append)

        reader.start()
        deadline = time.monotonic() + 1.0
        while not accesses and time.monotonic() < deadline:
            time.sleep(0.001)
        reader.stop()

        assert accesses == [access]
        assert not reader.is_alive()
        assert reader.error is None

    def test_telemetry_reader_reports_access_callback_errors(self, mocker) -> None:
        """Verify callback failures stop the reader and remain observable by the recorder."""
        telemetry = mocker.MagicMock(spec=Telemetry)
        telemetry.descriptor = ETHERCAT_TELEMETRY
        access = (1).to_bytes(ETHERCAT_TELEMETRY.frame_count_size, "little") + b"payload"
        telemetry.read_access.return_value = access
        error = RuntimeError("sink failed")
        reader = TelemetryReader(
            telemetry,
            poll_interval=0.001,
            on_access=mocker.Mock(side_effect=error),
        )

        reader.start()
        deadline = time.monotonic() + 1.0
        while reader.is_alive() and time.monotonic() < deadline:
            time.sleep(0.001)
        reader.stop()

        assert reader.error is error


class TestTelemetrySession:
    """Unit tests for ``TelemetrySession`` lifecycle guards, against a mocked transport."""

    @staticmethod
    def _session(mocker, tmp_path) -> TelemetrySession:
        """Build a session with the servo transport and Rust sinks mocked out.

        Returns:
            A ``TelemetrySession`` whose ``start()`` never touches real hardware or files.
        """
        servo = mocker.MagicMock(spec=Servo)
        telemetry = mocker.MagicMock(spec=Telemetry)
        telemetry.descriptor = ETHERCAT_TELEMETRY
        telemetry.configure.return_value = 1_000
        telemetry.recommended_poll_interval.return_value = 0.01
        servo.telemetry.return_value = telemetry
        mocker.patch("ingenialink.telemetry.TelemetryParquetRecorder")
        mocker.patch("ingenialink.telemetry.TelemetryDecoder")
        mocker.patch("ingenialink.telemetry.TelemetryReader")
        register = _fake_register(mocker, "REG", RegDtype.U16)
        register.monitoring = mocker.MagicMock(subnode=0, address=1)
        return TelemetrySession(servo, [register], tmp_path / "telemetry.parquet")

    def test_telemetry_session_double_start_raises(self, mocker, tmp_path) -> None:
        """Verify starting an already-running session raises."""
        session = self._session(mocker, tmp_path)
        session.start()

        with pytest.raises(RuntimeError, match="already running"):
            session.start()

    def test_telemetry_session_pause_without_start_raises(self, mocker, tmp_path) -> None:
        """Verify pausing a session that never started raises."""
        session = self._session(mocker, tmp_path)

        with pytest.raises(RuntimeError, match="not running"):
            session.pause()

    def test_telemetry_session_add_marker_before_start_raises(self, mocker, tmp_path) -> None:
        """Verify adding a marker before recording starts raises."""
        session = self._session(mocker, tmp_path)

        with pytest.raises(RuntimeError, match="not started"):
            session.add_marker("too early")


RECORDING_DURATION_S = 10.0
COMPLETE_ACCESS_BUFFER_SIZES = (1_024, 2_048, 4_096, 8_192, 16_384, 32_768)


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
        with TelemetrySession(
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
        "drive_timestamp",
        "timestamp_segment",
        "host_time",
        "FBK_GEN_VALUE",
        "DRV_PROT_VBUS_VALUE",
        "FBK_CUR_A_VALUE",
    ]
    timestamps = table.column("timestamp").to_pylist()
    assert timestamps == sorted(timestamps)
    return table


@pytest.mark.ethercat
# Telemetry firmware is only implemented on Capitan EtherCAT.
@pytest.mark.not_valid_for_product(part_number="EVE-*")
@pytest.mark.not_valid_for_product(part_number="DEN-*")
@pytest.mark.not_valid_for_product(part_number="*-C-*")
class TestEthercatTelemetryHardware:
    """Integration tests against a real EtherCAT drive's telemetry firmware."""

    def test_telemetry_configures_and_reads_raw_access(self, telemetry_servo) -> None:
        """Verify that an EtherCAT drive produces a raw telemetry access."""
        telemetry = telemetry_servo.telemetry()
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
                        access = telemetry.read_access()
                        frame = access
                        break
                    except ILRegisterAccessError:
                        pass
                time.sleep(0.01)
            assert frame is not None
            assert len(frame) >= telemetry.descriptor.frame_count_size + telemetry.sample_size()
        finally:
            telemetry.stop()

    def test_telemetry_firmware_timestamps_are_incremental(self, telemetry_servo) -> None:
        """Verify that firmware telemetry timestamps increase in arrival order."""
        telemetry = telemetry_servo.telemetry()
        register = _get_telemetry_test_register(telemetry_servo)
        telemetry.configure([register], desired_frequency=2_000)
        timestamps: list[int] = []

        try:
            telemetry.start()
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline and len(timestamps) < 100:
                with suppress(ILRegisterAccessError):
                    access = telemetry.read_access()
                    frame_count_size = telemetry.descriptor.frame_count_size
                    frame_size = telemetry._frame_size  # noqa: SLF001
                    timestamps.extend(
                        int.from_bytes(
                            access[offset : offset + telemetry.descriptor.timestamp_size],
                            "little",
                        )
                        for offset in range(
                            frame_count_size,
                            len(access),
                            frame_size,
                        )
                    )
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

    def test_telemetry_complete_access_buffer_size_sweep(self, telemetry_servo) -> None:
        """Find the largest complete-access buffer accepted by the drive."""
        telemetry = telemetry_servo.telemetry()
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

    @pytest.mark.parametrize("adaptive_rate", [False, True], ids=["fixed", "adaptive"])
    @pytest.mark.parametrize("telemetry_frequency_hz", [1_000.0, 5_000.0, 20_000.0])
    @pytest.mark.parametrize("generator_frequency_hz", [1.0, 5.0, 20.0])
    def test_telemetry_recorder_captures_internal_generator_saw_tooth_signal(
        self,
        servo,
        test_output_handler,
        generator_frequency_hz: float,
        telemetry_frequency_hz: float,
        adaptive_rate: bool,
    ) -> None:
        """Verify TelemetrySession captures a saw-tooth waveform from the internal generator.

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
            current - previous
            for previous, current in zip(generator_samples, generator_samples[1:])
        ]
        assert any(delta > 0 for delta in deltas), "Saw-tooth capture should show a rising ramp"
        assert any(delta < 0 for delta in deltas), "Saw-tooth capture should show a reset"

    @pytest.mark.parametrize("adaptive_rate", [False, True], ids=["fixed", "adaptive"])
    @pytest.mark.parametrize("telemetry_frequency_hz", [1_000.0, 5_000.0, 20_000.0])
    @pytest.mark.parametrize("generator_frequency_hz", [1.0, 5.0, 20.0])
    def test_telemetry_recorder_captures_internal_generator_square_signal(
        self,
        servo,
        test_output_handler,
        generator_frequency_hz: float,
        telemetry_frequency_hz: float,
        adaptive_rate: bool,
    ) -> None:
        """Verify TelemetrySession captures a square waveform from the internal generator.

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
            current - previous
            for previous, current in zip(generator_samples, generator_samples[1:])
        ]
        assert any(delta > 0 for delta in deltas), "Square capture should show a rising edge"
        assert any(delta < 0 for delta in deltas), "Square capture should show a falling edge"


class TestEthercatTelemetryVirtual:
    """Integration tests against the virtual drive's fake TEL_* firmware service."""

    @pytest.mark.parametrize("adaptive_rate", [False, True])
    def test_virtual_telemetry_configures_and_streams_frames(
        self, virtual_drive_ethercat_telemetry, adaptive_rate: bool
    ) -> None:
        """Verify telemetry sampling against a fake TEL_* firmware service."""
        _, _, servo = virtual_drive_ethercat_telemetry
        telemetry = Telemetry(servo, ETHERCAT_TELEMETRY)
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
            accesses: list[bytes] = []
            while time.monotonic() < deadline and len(accesses) < 20:
                with suppress(ILRegisterAccessError):
                    access = telemetry.read_access()
                    if int.from_bytes(access[:2], "little") > 0:
                        accesses.append(access)
                if len(accesses) < 20:
                    time.sleep(0.01)

            assert len(accesses) >= 20
            assert telemetry.sample_size() == 6  # s32 counter + u16 test channel

            for access in accesses:
                payload = access[2 + telemetry.descriptor.timestamp_size :]
                counter_value = int.from_bytes(payload[0:4], "little", signed=True)
                test_channel_value = int.from_bytes(payload[4:6], "little")
                assert counter_value == 0
                assert test_channel_value == 4321

            timestamps = [int.from_bytes(access[2:10], "little") for access in accesses]
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
        self, virtual_drive_ethercat_telemetry, tmp_path
    ) -> None:
        """Verify TelemetrySession end-to-end against a fake TEL_* firmware service."""
        _, _, servo = virtual_drive_ethercat_telemetry
        counter = servo.dictionary.get_register("DRV_DIAG_ERROR_LAST_COM", axis=0)
        path = tmp_path / "telemetry.parquet"

        with TelemetrySession(
            servo,
            [counter],
            path,
            frequency=2_000,
            batch_size=10,
        ):
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                if path.exists():
                    try:
                        if pq.read_table(path).num_rows >= 20:
                            break
                    except pa.ArrowInvalid:
                        pass
                time.sleep(0.01)

        table = pq.read_table(path)
        assert table.num_rows >= 20
        assert table.column_names == [
            "timestamp",
            "drive_timestamp",
            "timestamp_segment",
            "host_time",
            "DRV_DIAG_ERROR_LAST_COM",
        ]
        assert all(value == 0 for value in table.column("DRV_DIAG_ERROR_LAST_COM").to_pylist())
        timestamps = table.column("timestamp").to_pylist()
        assert timestamps == sorted(timestamps)

    def test_virtual_telemetry_recorder_pause_and_resume(
        self, virtual_drive_ethercat_telemetry, tmp_path
    ) -> None:
        """Verify pause/start against a fake TEL_* firmware service resumes into the same file."""
        _, _, servo = virtual_drive_ethercat_telemetry
        counter = servo.dictionary.get_register("DRV_DIAG_ERROR_LAST_COM", axis=0)
        path = tmp_path / "telemetry.parquet"

        recorder = TelemetrySession(
            servo,
            [counter],
            path,
            frequency=2_000,
            batch_size=10,
        )
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
