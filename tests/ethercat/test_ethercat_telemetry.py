import time
from contextlib import suppress

import pytest

from ingenialink.ethercat.servo import EthercatServo
from ingenialink.ethercat.telemetry import EthercatTelemetry, TelemetryFrame
from ingenialink.exceptions import ILRegisterAccessError


@pytest.mark.ethercat
def test_telemetry_configures_and_reads_frames(servo) -> None:
    """Verify that an EtherCAT drive produces raw telemetry frames."""
    telemetry = EthercatTelemetry(servo)
    register = servo.dictionary.get_register("DRV_PROT_VBUS_VALUE", axis=1)
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
def test_telemetry_firmware_timestamps_are_incremental(servo) -> None:
    """Verify that firmware telemetry timestamps increase in arrival order."""
    telemetry = EthercatTelemetry(servo)
    register = servo.dictionary.get_register("DRV_PROT_VBUS_VALUE", axis=1)
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


def test_telemetry_discards_incomplete_buffer_tail(mocker) -> None:
    """Verify that fixed-size EtherCAT responses may end with a partial frame."""
    servo = mocker.MagicMock(spec=EthercatServo)
    telemetry = EthercatTelemetry(servo)
    servo.read.return_value = 12
    servo.read_complete_access.return_value = (123).to_bytes(8, "little") + b"data" + b"tail"

    frames = telemetry.read_frames()

    assert frames == [TelemetryFrame(data=b"data", timestamp_tick=123)]
