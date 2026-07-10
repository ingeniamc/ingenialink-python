"""Create an offline deployment bundle for ingenialink.

The bundle is meant to be created on an online machine and copied to an offline
target machine.

It packages:
1. Runtime dependencies from ``pyproject.toml``.
2. A project artifact for ingenialink.

Resolution order is fixed and minimal:
1. Pure-Python wheels.
2. aarch64 Linux wheels.
3. Fail if neither wheel is available.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - fallback for Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
PYPROJECT_FILE = REPO_ROOT / "pyproject.toml"
LOGGER = logging.getLogger(__name__)


def load_project_version() -> str:
    """Load the current ingenialink version from ``ingenialink/_version.py``.

    Returns:
        Project version string.

    """
    version_file = REPO_ROOT / "ingenialink" / "_version.py"
    if not version_file.exists():
        return "unknown"

    content = version_file.read_text(encoding="utf-8")
    match = re.search(r"__version__\s*=\s*version\s*=\s*['\"]([^'\"]+)['\"]", content)
    if match is None:
        return "unknown"

    return match.group(1)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for bundle creation.

    Returns:
        Parsed CLI namespace.

    """
    parser = argparse.ArgumentParser(
        description="Bundle ingenialink and its runtime dependencies for offline install."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=SCRIPT_DIR / "offline_bundle",
        help="Directory where the bundle will be created.",
    )
    parser.add_argument(
        "--python-version",
        default="3.13",
        help=("Target Python version used for wheel downloads (for example: 3.11)."),
    )
    parser.add_argument(
        "--platform",
        default="manylinux2014_aarch64",
        help="Target platform tag for aarch64 wheel fallback (default is Linux aarch64).",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete the output directory before creating the bundle.",
    )
    return parser.parse_args()


def run(cmd: list[str], cwd: Path | None = None) -> None:
    """Run a command and raise on failure."""
    LOGGER.info("$ %s", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=cwd)


def load_runtime_dependencies(pyproject: Path) -> list[str]:
    """Read runtime dependencies from ``pyproject.toml``.

    Args:
        pyproject: Path to the project TOML file.

    Returns:
        Runtime dependency requirement strings.

    Raises:
        ValueError: If the dependencies section is missing or malformed.

    """
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    try:
        deps = data["project"]["dependencies"]
    except KeyError as exc:
        raise ValueError("No [project].dependencies found in pyproject.toml") from exc
    if not isinstance(deps, list) or not all(isinstance(dep, str) for dep in deps):
        raise ValueError("[project].dependencies must be a list of strings")
    return deps


def write_requirements_file(requirements: list[str], path: Path) -> None:
    """Write a plain pip requirements file."""
    content = "\n".join(requirements) + "\n"
    path.write_text(content, encoding="utf-8")


def load_pip_sources_from_pyproject(pyproject: Path) -> tuple[str | None, list[str]]:
    """Load pip-compatible index URLs from ``[tool.poetry.source]``.

    Args:
        pyproject: Path to project TOML file.

    Returns:
        Tuple with primary index URL (if explicitly defined) and extra index URLs.

    """
    with pyproject.open("rb") as f:
        data = tomllib.load(f)

    sources = data.get("tool", {}).get("poetry", {}).get("source", [])
    if not isinstance(sources, list):
        return None, []

    primary_index: str | None = None
    extras: list[str] = []

    for source in sources:
        if not isinstance(source, dict):
            continue
        source_url = source.get("url")
        priority = source.get("priority")

        # Poetry's primary source can be implicit PyPI without URL; skip those.
        if not isinstance(source_url, str):
            continue

        if priority == "primary" and primary_index is None:
            primary_index = source_url
            continue

        if priority in {"supplemental", "explicit", "secondary"}:
            extras.append(source_url)

    return primary_index, extras


def build_download_base_cmd(
    destination: Path,
    extra_index_urls: list[str] | None = None,
    trusted_hosts: list[str] | None = None,
) -> list[str]:
    """Build base ``pip download`` command with index configuration.

    Args:
        destination: Download destination directory.
        extra_index_urls: Extra package indexes.
        trusted_hosts: Hosts passed as trusted hosts.

    Returns:
        Base command for ``pip download``.

    """
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "--dest",
        str(destination),
    ]
    for extra_index_url in extra_index_urls or []:
        cmd.extend(["--extra-index-url", extra_index_url])
    for host in trusted_hosts or []:
        cmd.extend(["--trusted-host", host])
    return cmd


def trusted_hosts_from_urls(urls: list[str]) -> list[str]:
    """Extract trusted hosts from HTTP URLs.

    Args:
        urls: URLs to inspect.

    Returns:
        Deduplicated host list for ``--trusted-host``.

    """
    hosts: list[str] = []
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme == "http" and parsed.hostname:
            hosts.append(parsed.hostname)
    return list(dict.fromkeys(hosts))


def download_dependencies(
    requirements_file: Path,
    destination: Path,
    python_version: str,
    platform_tag: str,
) -> None:
    """Download dependency artifacts using the fixed wheel fallback order.

    Args:
        requirements_file: Requirements input file.
        destination: Directory where files are downloaded.
        python_version: Target Python version for wheel resolution.
        platform_tag: Target platform tag for wheel resolution.

    Raises:
        RuntimeError: If a dependency has neither a pure wheel nor an aarch64 wheel.

    """
    base_cmd = build_download_base_cmd(
        destination=destination,
    )

    for requirement in parse_requirements_file(requirements_file):
        download_wheel_with_fallback(
            requirement=requirement,
            base_cmd=base_cmd,
            python_version=python_version,
            platform_tag=platform_tag,
        )

    prune_duplicate_artifacts(destination)


def parse_requirements_file(requirements_file: Path) -> list[str]:
    """Parse requirement specifiers from a requirements file.

    Args:
        requirements_file: Path to requirements file.

    Returns:
        Normalized non-comment requirement lines.

    """
    entries: list[str] = []
    for raw in requirements_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(line)
    return entries


def normalize_dist_name(name: str) -> str:
    """Normalize a distribution name for comparisons.

    Args:
        name: Raw distribution name.

    Returns:
        Normalized distribution name.

    """
    return name.replace("_", "-").replace(".", "-").lower()


def parse_wheel_identity(filename: str) -> tuple[str, str] | None:
    """Parse ``(name, version)`` from a wheel filename.

    Args:
        filename: Wheel filename.

    Returns:
        Tuple with distribution name and version, or ``None`` if parsing fails.

    """
    if not filename.endswith(".whl"):
        return None
    stem = filename[:-4]
    parts = stem.split("-")
    if len(parts) < 5:
        return None
    return normalize_dist_name(parts[0]), parts[1]


def build_pure_wheel_only_cmd(base_cmd: list[str], requirement: str) -> list[str]:
    """Build a pip command that only accepts pure-Python wheels.

    Args:
        base_cmd: Shared pip download command options.
        requirement: Dependency requirement specifier.

    Returns:
        Pip command configured to resolve only pure-Python wheel tags.

    """
    return [
        *base_cmd,
        requirement,
        "--only-binary",
        ":all:",
        "--platform",
        "any",
        "--implementation",
        "py",
        "--abi",
        "none",
    ]


def build_aarch64_wheel_cmd(
    base_cmd: list[str],
    requirement: str,
    python_version: str,
    platform_tag: str,
) -> list[str]:
    """Build a pip command that accepts target-specific aarch64 wheels.

    Args:
        base_cmd: Shared pip download command options.
        requirement: Dependency requirement specifier.
        python_version: Target Python version (for example ``3.12``).
        platform_tag: Target platform tag (for example ``manylinux2014_aarch64``).

    Returns:
        Pip command configured to resolve platform-specific wheels.

    """
    py_major, py_minor = python_version.split(".", maxsplit=1)
    py_no_dot = f"{py_major}{py_minor}"
    return [
        *base_cmd,
        requirement,
        "--only-binary",
        ":all:",
        "--platform",
        platform_tag,
        "--implementation",
        "cp",
        "--python-version",
        py_no_dot,
    ]


def download_wheel_with_fallback(
    requirement: str,
    base_cmd: list[str],
    python_version: str,
    platform_tag: str,
) -> None:
    """Download one requirement using the fixed wheel-only fallback order.

    Resolution order:
    1. Pure-Python wheel.
    2. aarch64 Linux wheel.

    Args:
        requirement: Requirement specifier.
        base_cmd: Shared pip command options.
        python_version: Target Python version.
        platform_tag: Target platform tag.

    Raises:
        RuntimeError: If no supported wheel is available.

    """
    pure_wheel_cmd = build_pure_wheel_only_cmd(base_cmd=base_cmd, requirement=requirement)
    try:
        run_pip_download_with_hint(pure_wheel_cmd)
        return
    except RuntimeError:
        LOGGER.warning(
            "No pure-Python wheel available for %s. Trying target aarch64 wheel.",
            requirement,
        )

    target_wheel_cmd = build_aarch64_wheel_cmd(
        base_cmd=base_cmd,
        requirement=requirement,
        python_version=python_version,
        platform_tag=platform_tag,
    )
    try:
        run_pip_download_with_hint(target_wheel_cmd)
        return
    except RuntimeError:
        LOGGER.warning(
            "No aarch64 wheel available for %s.",
            requirement,
        )
        raise RuntimeError(
            f"No supported wheel found for {requirement}. Expected a pure-Python or aarch64 wheel."
        )


def prune_duplicate_artifacts(destination: Path) -> None:
    """Keep only one artifact per package version.

    Preference order for the same package/version:
    1) pure-Python wheel
    2) any other wheel

    Args:
        destination: Directory containing downloaded dependency artifacts.

    """
    selected: dict[tuple[str, str], tuple[int, Path]] = {}
    extras: list[Path] = []

    for artifact in sorted(destination.iterdir()):
        if not artifact.is_file():
            continue

        identity = parse_wheel_identity(artifact.name)
        priority = 2 if "-none-any.whl" in artifact.name else 1

        if identity is None:
            continue

        key = identity
        current = selected.get(key)
        if current is None or priority > current[0]:
            if current is not None:
                extras.append(current[1])
            selected[key] = (priority, artifact)
        else:
            extras.append(artifact)

    for path in extras:
        if path.exists():
            path.unlink()


def build_local_wheel(destination: Path) -> None:
    """Build a local wheel for ingenialink into ``destination``."""
    run([
        sys.executable,
        "-m",
        "pip",
        "wheel",
        str(REPO_ROOT),
        "--no-deps",
        "--wheel-dir",
        str(destination),
    ])


def build_local_sdist(destination: Path) -> Path:
    """Build a local source distribution using the repository build task.

    Args:
        destination: Directory where the built source artifact is copied.

    Returns:
        Path to the copied source artifact.

    Raises:
        RuntimeError: If no source distribution artifact is produced.

    """
    dist_dir = REPO_ROOT / "dist"
    run(["poetry", "run", "poe", "build-wheel"], cwd=REPO_ROOT)

    sdist_candidates = sorted(
        dist_dir.glob("ingenialink-*.tar.gz"),
        key=lambda path: path.stat().st_mtime,
    )
    if not sdist_candidates:
        raise RuntimeError("No source distribution artifact was produced for ingenialink")

    source_artifact = sdist_candidates[-1]
    destination_artifact = destination / source_artifact.name
    shutil.copy2(source_artifact, destination_artifact)
    return destination_artifact


def load_local_project_build_requirements() -> list[str]:
    """Read local project's ``build-system.requires`` requirements.

    Returns:
        Requirement strings required to build local source.

    """
    with PYPROJECT_FILE.open("rb") as f:
        data = tomllib.load(f)
    build_requires = data.get("build-system", {}).get("requires", [])
    if not isinstance(build_requires, list):
        return []
    return [item for item in build_requires if isinstance(item, str)]


def ensure_local_project_build_requirements(
    base_cmd: list[str],
    python_version: str,
    platform_tag: str,
) -> None:
    """Download build requirements needed for local ingenialink source build.

    Args:
        base_cmd: Shared pip command options.
        python_version: Target Python version.
        platform_tag: Target platform tag.

    """
    for requirement in load_local_project_build_requirements():
        if "://" in requirement:
            run_pip_download_with_hint([*base_cmd, requirement, "--no-deps"])
            continue

        download_wheel_with_fallback(
            requirement=requirement,
            base_cmd=base_cmd,
            python_version=python_version,
            platform_tag=platform_tag,
        )


def package_project_artifact(
    project_destination: Path,
    base_cmd: list[str],
    python_version: str,
    platform_tag: str,
) -> Path:
    """Package the ingenialink project artifact.

    Args:
        project_destination: Directory for project artifacts.
        base_cmd: Shared pip command options.
        python_version: Target Python version.
        platform_tag: Target platform tag.

    Returns:
        Path to packaged project artifact.

    Raises:
        RuntimeError: If a required wheel artifact cannot be produced.

    """
    project_version = load_project_version()
    requirement = f"ingenialink=={project_version}"

    pyproject_index, pyproject_extras = load_pip_sources_from_pyproject(PYPROJECT_FILE)
    if pyproject_index or pyproject_extras:
        pyproject_hosts = trusted_hosts_from_urls([
            u for u in [pyproject_index, *pyproject_extras] if u
        ])
        retry_base_cmd = build_download_base_cmd(
            destination=project_destination,
            extra_index_urls=([pyproject_index] if pyproject_index else []) + pyproject_extras,
            trusted_hosts=pyproject_hosts,
        )
        retry_cmd = [
            *build_pure_wheel_only_cmd(base_cmd=retry_base_cmd, requirement=requirement),
            "--no-deps",
        ]
        before_retry_files = {p.name for p in project_destination.iterdir() if p.is_file()}
        try:
            run_pip_download_with_hint(retry_cmd)
            retry_new_files = sorted(
                {p.name for p in project_destination.iterdir() if p.is_file()} - before_retry_files
            )
            retry_wheels = [
                name
                for name in retry_new_files
                if name.endswith(".whl") and "-none-any.whl" in name
            ]
            if retry_wheels:
                LOGGER.info("Found ingenialink wheel using pyproject sources.")
                return project_destination / retry_wheels[0]
        except RuntimeError:
            LOGGER.warning(
                "No pure-Python wheel found for local ingenialink version %s in pyproject sources.",
                project_version,
            )
    else:
        LOGGER.warning("No pyproject package sources configured for ingenialink wheel lookup.")

    LOGGER.warning(
        "No pure-Python wheel found for local ingenialink version %s. Falling back to source.",
        project_version,
    )
    source_path = build_local_sdist(project_destination)
    ensure_local_project_build_requirements(
        base_cmd=base_cmd,
        python_version=python_version,
        platform_tag=platform_tag,
    )
    return source_path


def write_metadata(path: Path, metadata: dict[str, Any]) -> None:
    """Write JSON metadata describing the generated bundle."""
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    """Create an offline-ready deployment bundle and emit installation hints.

    Returns:
        Process exit code.

    Raises:
        RuntimeError: If bundle artifacts cannot be generated as requested.

    """
    args = parse_args()

    if args.clean and args.output_dir.exists():
        shutil.rmtree(args.output_dir)

    deps_dir = args.output_dir / "dependencies"
    project_dir = args.output_dir / "project"
    meta_dir = args.output_dir / "metadata"

    deps_dir.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    runtime_deps = load_runtime_dependencies(PYPROJECT_FILE)
    requirements_file = meta_dir / "requirements-runtime.txt"
    write_requirements_file(runtime_deps, requirements_file)

    base_cmd = build_download_base_cmd(
        destination=deps_dir,
    )

    download_dependencies(
        requirements_file=requirements_file,
        destination=deps_dir,
        python_version=args.python_version,
        platform_tag=args.platform,
    )

    project_artifact = package_project_artifact(
        project_destination=project_dir,
        base_cmd=base_cmd,
        python_version=args.python_version,
        platform_tag=args.platform,
    )

    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(REPO_ROOT),
        "target_platform": args.platform,
        "target_python_version": args.python_version,
        "requirements_file": str(requirements_file.relative_to(args.output_dir)),
        "project_artifact": str(project_artifact.relative_to(args.output_dir)),
        "dependency_files": sorted(p.name for p in deps_dir.iterdir() if p.is_file()),
    }
    write_metadata(meta_dir / "bundle-metadata.json", metadata)

    LOGGER.info("Offline bundle created: %s", args.output_dir)
    LOGGER.info("Install on offline target with:")
    LOGGER.info(
        "  python -m pip install --no-index --find-links dependencies "
        "-r metadata/requirements-runtime.txt"
    )
    LOGGER.info("  python -m pip install --no-index --find-links project <PROJECT_ARTIFACT>")

    return 0


def run_pip_download_with_hint(cmd: list[str]) -> None:
    """Run pip download and provide actionable hints for private-index failures.

    Args:
        cmd: Prepared pip command.

    Raises:
        RuntimeError: With guidance if download fails.

    """
    try:
        run(cmd)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Dependency download failed. Check whether the package exists on PyPI or "
            "the Novanta package source configured in pyproject.toml."
        ) from exc


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
