# Agents Documentation

This file is reserved for notes, documentation, and references about agents used in this repository. Use this file to track agent patterns, usage, and best practices.

## Usage
- Add agent-related design notes, implementation details, or conventions here.
- Reference this file in code comments or PRs when agent logic is updated.

## Styling Preferences
- Always keep python imports at the top of every file.

## Linting
- Use the `poe` tasks defined in `pyproject.toml` to run linters and type checks after every code change.
- Recommended `poe` commands (defined under `[tool.poe.tasks]`):
	- `poe format` — format check (runs ruff format --check and ruff check).
	- `poe reformat` — reformat and fix lint errors (runs ruff format and ruff check --fix).
	- `poe ruff-check` — run ruff linting only.
	- `poe ruff-check-fix` — run ruff with `--fix` to apply lint fixes.
	- `poe type` — run mypy type checks.
