# Offline deployment bundle for ingenialink

This folder contains tooling to prepare an offline installation package for
Linux aarch64 targets.

The workflow is:

1. Run the bundling script on a machine with internet access.
2. Copy the generated `offline_bundle` directory to the offline target.
3. Install dependencies and ingenialink from local files only.

## Script

Use `deployment_evk/bundle_offline.py` from the repository root.

The script uses standard PyPI for runtime dependencies.

For the `ingenialink` project artifact, wheel lookup goes directly to the
Poetry sources configured in `pyproject.toml` (for example Novanta PyPI).

### Build the bundle

```bash
python deployment_evk/bundle_offline.py --clean
```

The script uses one fixed strategy for all packages:

1. Try a pure-Python wheel.
2. If not available, try an aarch64 Linux wheel.
3. If neither exists, log it and continue.

This avoids source builds for runtime dependencies.

For the `ingenialink` project artifact, the script tries pure wheel lookup in
`tool.poetry.source` indexes (for example Novanta PyPI) using this sequence:

1. Local SCM-generated version from `ingenialink/_version.py`.
2. Base release version from `[tool.poetry].version`.
3. Unpinned `ingenialink` (latest wheel available in configured sources).

If no pure-Python wheel exists, it falls back to a versioned local source
archive and also downloads local project `build-system.requires` dependencies.

The output is minimized to one artifact per package version.

## Bundle structure

After running the script, you will get:

- `deployment/offline_bundle/dependencies`: runtime dependency artifacts
- `deployment/offline_bundle/project`: ingenialink artifact
- `deployment/offline_bundle/metadata/requirements-runtime.txt`: pinned runtime requirements from `pyproject.toml`
- `deployment/offline_bundle/metadata/bundle-metadata.json`: bundle metadata

The metadata file includes `missing_runtime_dependency_wheels` so you can see
which runtime dependencies could not be bundled as wheels.

## Offline install on target

From inside the copied `offline_bundle` directory:

```bash
python -m pip install --no-index --find-links dependencies -r metadata/requirements-runtime.txt
python -m pip install --no-index --find-links project project/<PROJECT_ARTIFACT>
```

Replace `<PROJECT_ARTIFACT>` with the actual file name inside `project`.

## Notes

- The default flow is wheel-only: pure-Python first, then aarch64.
- Runtime dependency wheel misses are reported and do not stop bundle generation.
- Only the `ingenialink` project artifact may fall back to source.
