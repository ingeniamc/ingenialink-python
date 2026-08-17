"""Generate type stubs for the native ingenialink extension."""

import os
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIRECTORY = PROJECT_ROOT / "ingenialink" / "_rust"


def main() -> None:
    """Build the extension and generate its stubs.

    Raises:
        RuntimeError: If the introspection executable is unavailable.
    """
    introspection = os.environ.get("PYO3_INTROSPECTION_BIN") or shutil.which("pyo3-introspection")
    if introspection is None:
        raise RuntimeError(
            "pyo3-introspection is required; install the matching 0.29.x binary "
            "with `cargo install pyo3-introspection --version 0.29.2`."
        )

    subprocess.run(
        ["cargo", "build", "--features", "abi3,inspect"],
        cwd=PROJECT_ROOT,
        check=True,
    )
    binary = next(
        path
        for pattern in ("lib_rust.so", "lib_rust.dylib", "_rust.dll")
        for path in [(PROJECT_ROOT / "target" / "debug" / pattern)]
        if path.exists()
    )
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [introspection, str(binary), "_rust", str(OUTPUT_DIRECTORY)],
        cwd=PROJECT_ROOT,
        check=True,
    )


if __name__ == "__main__":
    main()
