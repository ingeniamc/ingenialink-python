import time

import pytest

from ingenialink.ethercat.telemetry import EthercatTelemetry
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
