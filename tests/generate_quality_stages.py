import argparse
import json
from pathlib import Path


def main():
    """Generate quality stages JSON configuration."""

    parser = argparse.ArgumentParser(
        description="Generate quality stages configuration for Jenkins pipeline"
    )
    parser.add_argument(
        "--output_file",
        default="test_quality_stages.json",
        help="Optional output file to write the configuration (defaults to stdout)",
    )
    args = parser.parse_args()

    # Define quality check tasks from pyproject.toml
    quality_tasks = {
        "Format Check": [
            {
                "name": "Ruff Format Check",
                "command": "poetry run poe ruff-format-check",
                "description": "Check code formatting with ruff",
            },
            {
                "name": "Ruff Lint Check",
                "command": "poetry run poe ruff-check",
                "description": "Check code quality with ruff linter",
            },
        ],
        "Type Check": [
            {
                "name": "MyPy Type Check",
                "command": "poetry run poe type",
                "description": "Run static type checking with mypy",
            }
        ],
        "Auto-fix (Optional)": [
            {
                "name": "Ruff Format (Fix)",
                "command": "poetry run poe ruff-format",
                "description": "Auto-format code with ruff",
            },
            {
                "name": "Ruff Lint (Fix)",
                "command": "poetry run poe ruff-check-fix",
                "description": "Auto-fix lint errors with ruff",
            },
        ],
    }

    # Build configuration
    config = {
        "version": "1.0",
        "description": (
            "Quality check stages configuration for automated Jenkins pipeline generation"
        ),
        "stages": {},
    }

    # Convert to stages format
    for stage_name, tasks in quality_tasks.items():
        config["stages"][stage_name] = {"tasks": tasks}

    # Write to file or stdout
    output = json.dumps(config, indent=2)

    # Check if output file specified as argument
    import sys

    output_file = Path(args.output_file)
    output_file.write_text(output)
    print(f"Generated quality stages configuration: {output_file}", file=sys.stderr)  # noqa: T201


if __name__ == "__main__":
    main()
