import time
from contextlib import suppress

import pytest

from ingenialink.enums.register import RegDtype
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.ethercat.telemetry import (
    EthercatTelemetry,
    TelemetryFrame,
    TelemetryPoller,
    TelemetrySample,
)
from ingenialink.exceptions import ILRegisterAccessError
from ingenialink.register import Register


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


def test_telemetry_poller_decodes_multiple_registers_from_one_frame(mocker) -> None:
    """Verify that one frame decodes multiple mixed-width register values."""
    telemetry = mocker.MagicMock(spec=EthercatTelemetry)
    telemetry.TIMESTAMP_FREQUENCY_HZ = 1_000_000
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
        data=(123).to_bytes(2, "little")
        + (456).to_bytes(4, "little")
        + (7).to_bytes(1, "little"),
        timestamp_tick=2_000,
    )
    poller = TelemetryPoller(
        telemetry, [first_register, second_register, third_register]
    )

    def read_one_frame() -> list[TelemetryFrame]:
        poller._stop_event.set()
        return [frame]

    telemetry.read_frames.side_effect = read_one_frame
    poller.start()
    poller.join(timeout=1.0)

    assert not poller.is_alive()
    assert poller.sample_count == 1
    assert poller.get_sample() == TelemetrySample(
        timestamp=0.002,
        values={
            "FIRST_REGISTER": 123,
            "SECOND_REGISTER": 456,
            "THIRD_REGISTER": 7,
        },
    )
