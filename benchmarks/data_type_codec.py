"""Benchmark the legacy Python data-type conversion functions.

Run from this worktree with:

    PYTHONPATH=. .venv/bin/python benchmarks/data_type_codec.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from timeit import repeat
from typing import TYPE_CHECKING

from ingenialink.enums.register import RegDtype
from ingenialink.utils._utils import convert_bytes_to_dtype, convert_dtype_to_bytes

if TYPE_CHECKING:
    from collections.abc import Callable

_ITERATIONS = 100_000
_REPEATS = 3


@dataclass(frozen=True)
class BenchmarkCase:
    """Representative valid input for one register data type."""

    name: str
    dtype: RegDtype
    value: float | int | str | bytes
    payload: bytes


_CASES = (
    BenchmarkCase("U8", RegDtype.U8, 0x7F, b"\x7f"),
    BenchmarkCase("S8", RegDtype.S8, -42, b"\xd6"),
    BenchmarkCase("U16", RegDtype.U16, 0x1234, b"\x34\x12"),
    BenchmarkCase("S16", RegDtype.S16, -1234, b"\x2e\xfb"),
    BenchmarkCase("U32", RegDtype.U32, 0x1234_5678, b"\x78\x56\x34\x12"),
    BenchmarkCase("S32", RegDtype.S32, -123_456_789, b"\xeb\x32\xa4\xf8"),
    BenchmarkCase(
        "U64",
        RegDtype.U64,
        0x1234_5678_9ABC_DEF0,
        b"\xf0\xde\xbc\x9a\x78\x56\x34\x12",
    ),
    BenchmarkCase(
        "S64",
        RegDtype.S64,
        -1_234_567_890_123_456_789,
        b"\xeb\x7e\x16\x82\x0b\xef\xee\xee",
    ),
    BenchmarkCase("FLOAT", RegDtype.FLOAT, 34.5, b"\x00\x00\x0a\x42"),
    BenchmarkCase("STR", RegDtype.STR, "codec benchmark", b"codec benchmark\x00ignored"),
    BenchmarkCase(
        "BYTE_ARRAY_512",
        RegDtype.BYTE_ARRAY_512,
        bytes(range(256)) * 2,
        bytes(range(256)) * 2,
    ),
    BenchmarkCase("BOOL", RegDtype.BOOL, True, b"\x01"),
)


def _nanoseconds_per_call(function: Callable[[], object]) -> float:
    """Return the best scalar timing in nanoseconds per invocation."""
    return min(repeat(function, number=_ITERATIONS, repeat=_REPEATS)) * 1_000_000_000 / _ITERATIONS


def main() -> None:
    """Run the legacy conversion benchmark."""
    sys.stdout.write("data type       develop legacy\n")
    sys.stdout.write("                enc/dec\n")
    for case in _CASES:
        encode = _nanoseconds_per_call(lambda: convert_dtype_to_bytes(case.value, case.dtype))
        decode = _nanoseconds_per_call(lambda: convert_bytes_to_dtype(case.payload, case.dtype))
        sys.stdout.write(f"{case.name:15} {encode:5.0f}/{decode:5.0f}\n")


if __name__ == "__main__":
    main()
