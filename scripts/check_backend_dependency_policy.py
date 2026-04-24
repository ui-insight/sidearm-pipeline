#!/usr/bin/env python3
"""Validate backend dependency policy across requirements and pyproject files."""

from __future__ import annotations

import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

try:
    from packaging.version import Version as PackagingVersion
except ImportError:  # pragma: no cover - fallback for minimal Python envs.
    PackagingVersion = None


ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS_PATH = ROOT / "backend" / "requirements.txt"
PYPROJECT_PATH = ROOT / "backend" / "pyproject.toml"

DEPENDENCY_PATTERN = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)"
    r"(?P<extras>\[[A-Za-z0-9_,.-]+\])?"
    r"(?P<operator>==|>=)"
    r"(?P<version>[A-Za-z0-9_.+-]+)$"
)
NUMERIC_VERSION_PATTERN = re.compile(r"^\d+(?:\.\d+)*$")


@dataclass(frozen=True)
class DependencySpec:
    """Single dependency specifier from requirements.txt or pyproject.toml."""

    normalized_name: str
    display_name: str
    operator: str
    version: str
    source_text: str


def normalize_name(name: str, extras: str | None) -> tuple[str, str]:
    """Normalize package names so equivalent extras compare cleanly."""
    base_name = name.lower().replace("_", "-")
    if not extras:
        return base_name, base_name

    normalized_extras = ",".join(
        sorted(extra.strip().lower().replace("_", "-") for extra in extras[1:-1].split(","))
    )
    display_name = f"{base_name}[{normalized_extras}]"
    return display_name, display_name


def parse_dependency_spec(raw_spec: str, allowed_operators: set[str]) -> DependencySpec:
    """Parse a simple dependency specifier and validate the operator."""
    match = DEPENDENCY_PATTERN.fullmatch(raw_spec.strip())
    if not match:
        raise ValueError(
            "Unsupported dependency specifier format: "
            f"{raw_spec!r}. Use simple pinned (==) or minimum (>=) versions."
        )

    operator = match.group("operator")
    if operator not in allowed_operators:
        allowed = ", ".join(sorted(allowed_operators))
        raise ValueError(
            f"Unsupported operator {operator!r} in {raw_spec!r}. Expected one of: {allowed}."
        )

    normalized_name, display_name = normalize_name(
        match.group("name"), match.group("extras")
    )
    return DependencySpec(
        normalized_name=normalized_name,
        display_name=display_name,
        operator=operator,
        version=match.group("version"),
        source_text=raw_spec.strip(),
    )


def parse_requirements_sections(path: Path) -> tuple[dict[str, DependencySpec], dict[str, DependencySpec]]:
    """Split requirements.txt into runtime and development sections."""
    runtime_dependencies: dict[str, DependencySpec] = {}
    dev_dependencies: dict[str, DependencySpec] = {}
    current_section = runtime_dependencies

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#"):
            if "development / testing" in line.lower():
                current_section = dev_dependencies
            continue

        dependency = parse_dependency_spec(line, allowed_operators={"=="})
        current_section[dependency.normalized_name] = dependency

    return runtime_dependencies, dev_dependencies


def parse_pyproject_sections(path: Path) -> tuple[dict[str, DependencySpec], dict[str, DependencySpec]]:
    """Read runtime and dev dependency declarations from pyproject.toml."""
    pyproject = tomllib.loads(path.read_text(encoding="utf-8"))
    project = pyproject["project"]

    runtime_dependencies = {
        dependency.normalized_name: dependency
        for dependency in (
            parse_dependency_spec(raw_spec, allowed_operators={">="})
            for raw_spec in project.get("dependencies", [])
        )
    }
    dev_dependencies = {
        dependency.normalized_name: dependency
        for dependency in (
            parse_dependency_spec(raw_spec, allowed_operators={">="})
            for raw_spec in project.get("optional-dependencies", {}).get("dev", [])
        )
    }

    return runtime_dependencies, dev_dependencies


def compare_versions(pinned_version: str, minimum_version: str) -> bool:
    """Return True when the pinned version is at least the declared minimum."""
    if PackagingVersion is not None:
        return PackagingVersion(pinned_version) >= PackagingVersion(minimum_version)

    if not NUMERIC_VERSION_PATTERN.fullmatch(pinned_version):
        raise ValueError(
            "Non-numeric pinned version encountered without packaging installed: "
            f"{pinned_version!r}."
        )
    if not NUMERIC_VERSION_PATTERN.fullmatch(minimum_version):
        raise ValueError(
            "Non-numeric minimum version encountered without packaging installed: "
            f"{minimum_version!r}."
        )

    pinned_parts = tuple(int(part) for part in pinned_version.split("."))
    minimum_parts = tuple(int(part) for part in minimum_version.split("."))
    max_length = max(len(pinned_parts), len(minimum_parts))
    padded_pinned = pinned_parts + (0,) * (max_length - len(pinned_parts))
    padded_minimum = minimum_parts + (0,) * (max_length - len(minimum_parts))
    return padded_pinned >= padded_minimum


def format_name_set(names: set[str]) -> str:
    """Format a normalized name set for error output."""
    return ", ".join(sorted(names))


def check_section(
    section_name: str,
    requirements_dependencies: dict[str, DependencySpec],
    pyproject_dependencies: dict[str, DependencySpec],
    errors: list[str],
) -> None:
    """Validate one dependency section."""
    requirements_names = set(requirements_dependencies)
    pyproject_names = set(pyproject_dependencies)

    requirements_only = requirements_names - pyproject_names
    pyproject_only = pyproject_names - requirements_names
    if requirements_only:
        errors.append(
            f"{section_name}: requirements.txt entries missing from pyproject.toml: "
            f"{format_name_set(requirements_only)}"
        )
    if pyproject_only:
        errors.append(
            f"{section_name}: pyproject.toml entries missing from requirements.txt: "
            f"{format_name_set(pyproject_only)}"
        )

    for dependency_name in sorted(requirements_names & pyproject_names):
        pinned_dependency = requirements_dependencies[dependency_name]
        minimum_dependency = pyproject_dependencies[dependency_name]
        if not compare_versions(pinned_dependency.version, minimum_dependency.version):
            errors.append(
                f"{section_name}: {pinned_dependency.display_name} is pinned to "
                f"{pinned_dependency.version} in requirements.txt but pyproject.toml "
                f"declares >= {minimum_dependency.version}"
            )


def main() -> int:
    """Run the backend dependency policy checks."""
    runtime_requirements, dev_requirements = parse_requirements_sections(REQUIREMENTS_PATH)
    runtime_pyproject, dev_pyproject = parse_pyproject_sections(PYPROJECT_PATH)

    errors: list[str] = []
    check_section("runtime", runtime_requirements, runtime_pyproject, errors)
    check_section("development", dev_requirements, dev_pyproject, errors)

    if errors:
        print("Backend dependency policy check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "Backend dependency policy check passed for "
        f"{len(runtime_requirements)} runtime and {len(dev_requirements)} "
        "development dependencies."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
