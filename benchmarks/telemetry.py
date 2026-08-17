"""Benchmark the develop branch Python telemetry decoder.

Run from this worktree with:

    PYTHONPATH=. .venv/bin/python benchmarks/telemetry.py
"""

from __future__ import annotations

import argparse
import struct
import sys
from time import perf_counter
from typing import TYPE_CHECKING

from ingenialink.enums.register import RegDtype

if TYPE_CHECKING:
    from collections.abc import Sequence

from ingenialink.ethercat.telemetry import TelemetryFrame, TelemetryPoller

_FRAMES_PER_ACCESS = 100


class _Register:
    """Minimal register implementation for the decoder benchmark."""

    def __init__(self, identifier: str, dtype: RegDtype, format_string: str) -> None:
        self.identifier = identifier
        self.dtype = dtype
        self._format_string = format_string

    def bytes_to_value(self, payload: bytes | memoryview) -> float | int:
        """Decode one fixed-width register payload.

        Returns:
            The decoded register value.
        """
        return struct.unpack(self._format_string, bytes(payload))[0]


class _Telemetry:
    """Minimal configured telemetry service for the decoder benchmark."""

    descriptor = type("Descriptor", (), {"timestamp_frequency_hz": 1_000_000.0})()

    def recommended_poll_interval(self, buffer_fill_ratio: float = 0.5) -> float:
        """Return a valid poll interval for the poller constructor."""
        del buffer_fill_ratio
        return 0.01


_REGISTERS = (
    _Register("u16", RegDtype.U16, "<H"),
    _Register("s32", RegDtype.S32, "<i"),
    _Register("float", RegDtype.FLOAT, "<f"),
)


def _make_frames(sample_count: int) -> list[TelemetryFrame]:
    """Create deterministic timestamped frames for the benchmark.

    Returns:
        Timestamped telemetry frames.
    """
    frames: list[TelemetryFrame] = []
    for sample in range(sample_count):
        payload = struct.pack("<Hif", sample & 0xFFFF, sample, sample * 0.25)
        frames.append(TelemetryFrame(payload, sample * 1_000))
    return frames


def _decode(frames: Sequence[TelemetryFrame]) -> None:
    """Decode all frames using the develop branch Python poller."""
    poller = TelemetryPoller(_Telemetry(), _REGISTERS, poll_interval=0.01)
    for frame in frames:
        poller._decode_frame(frame)


def main() -> None:
    """Run the develop branch telemetry benchmark."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=100_000)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.samples <= 0 or args.repeats <= 0:
        parser.error("--samples and --repeats must be positive")

    frames = _make_frames(args.samples)
    timings = []
    for _ in range(args.repeats):
        start = perf_counter()
        _decode(frames)
        timings.append(perf_counter() - start)
    elapsed = min(timings)
    sys.stdout.write(
        f"samples={args.samples:,}, frames/access={_FRAMES_PER_ACCESS}\n"
        f"Python decode             {elapsed:8.4f} s  "
        f"{args.samples / elapsed:12,.0f} samples/s\n"
    )


if __name__ == "__main__":
    main()
