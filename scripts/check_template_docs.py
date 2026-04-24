#!/usr/bin/env python3
"""Validate TEMPLATE-app documentation integrity checks.

This script intentionally supports both the template repository itself and
projects created from it:

- template placeholders are allowed only in a small set of known template files
- MkDocs navigation entries must point to files that actually exist
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MKDOCS_PATH = REPO_ROOT / "mkdocs.yml"
PLACEHOLDER_RE = re.compile(r"\{\{[A-Z_]+\}\}")
AGENT_GUIDE_PATHS = (Path("CLAUDE.md"), Path("AGENTS.md"))
CUSTOMIZABLE_PROJECT_NAME_FILES = {
    Path("AGENTS.md"),
    Path("CLAUDE.md"),
    Path("README.md"),
    Path(".env.example"),
    Path("backend/app/config.py"),
    Path("backend/app/main.py"),
    Path("backend/pyproject.toml"),
    Path("docs/architecture/overview.md"),
    Path("docs/governance/data-classification.md"),
    Path("docs/governance/data-governance.md"),
    Path("docs/index.md"),
    Path("docs/security/overview.md"),
    Path("e2e/tests/home.spec.ts"),
    Path("frontend/index.html"),
    Path("frontend/src/pages/HomePage.tsx"),
    Path("frontend/tests/HomePage.test.tsx"),
}

ALLOWED_TEMPLATE_PLACEHOLDER_FILES = {
    Path("AGENTS.md"),
    Path("CLAUDE.md"),
    Path("CONTRIBUTING.md"),
    Path("README.md"),
    Path(".env.example"),
    Path("backend/app/config.py"),
    Path("backend/app/main.py"),
    Path("backend/pyproject.toml"),
    Path("docs/architecture/overview.md"),
    Path("docs/contributing/getting-started.md"),
    Path("docs/adr/001-template-customization.md"),
    Path("docs/governance/data-classification.md"),
    Path("docs/governance/data-governance.md"),
    Path("docs/index.md"),
    Path("docs/security/overview.md"),
    Path("e2e/tests/home.spec.ts"),
    Path("frontend/index.html"),
    Path("frontend/src/pages/HomePage.tsx"),
    Path("frontend/tests/HomePage.test.tsx"),
    Path("mkdocs.yml"),
    Path("scripts/customize_template.py"),
}
REQUIRED_TEMPLATE_FILES = {
    Path(".github/CODEOWNERS"),
    Path("AGENTS.md"),
    Path("CLAUDE.md"),
    Path("README.md"),
}


def _tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line.strip()]


def _find_unexpected_placeholders(files: list[Path]) -> list[str]:
    failures: list[str] = []
    for rel_path in files:
        abs_path = REPO_ROOT / rel_path
        if rel_path.is_dir() or not abs_path.exists():
            continue
        text = abs_path.read_text(encoding="utf-8")
        if not PLACEHOLDER_RE.search(text):
            continue
        if rel_path not in ALLOWED_TEMPLATE_PLACEHOLDER_FILES:
            failures.append(
                f"Unexpected template placeholder found in {rel_path}"
            )
    return failures


def _check_required_files_exist() -> list[str]:
    failures: list[str] = []
    for rel_path in sorted(REQUIRED_TEMPLATE_FILES, key=str):
        if not (REPO_ROOT / rel_path).exists():
            failures.append(f"Required template file is missing: {rel_path}")
    return failures


def _check_required_files_not_ignored() -> list[str]:
    failures: list[str] = []
    for rel_path in sorted(REQUIRED_TEMPLATE_FILES, key=str):
        result = subprocess.run(
            ["git", "check-ignore", "-q", "--no-index", str(rel_path)],
            cwd=REPO_ROOT,
            check=False,
        )
        if result.returncode == 0:
            failures.append(f"Required template file is ignored by git: {rel_path}")
    return failures


def _shared_agent_guide_text(rel_path: Path) -> str | None:
    text = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    marker = "\n## Project Overview\n"
    marker_index = text.find(marker)
    if marker_index == -1:
        return None
    return text[marker_index + 1 :].replace("\r\n", "\n").strip()


def _check_agent_guides_synced() -> list[str]:
    failures: list[str] = []
    missing_files = [path for path in AGENT_GUIDE_PATHS if not (REPO_ROOT / path).exists()]
    if missing_files:
        missing = ", ".join(str(path) for path in missing_files)
        return [f"Missing agent guide file(s): {missing}"]

    normalized_texts: dict[Path, str] = {}
    for rel_path in AGENT_GUIDE_PATHS:
        normalized_text = _shared_agent_guide_text(rel_path)
        if normalized_text is None:
            failures.append(
                f"Agent guide missing '## Project Overview' section: {rel_path}"
            )
            continue
        normalized_texts[rel_path] = normalized_text

    if failures:
        return failures

    claude_text = normalized_texts[Path("CLAUDE.md")]
    agents_text = normalized_texts[Path("AGENTS.md")]
    if claude_text != agents_text:
        failures.append(
            "AGENTS.md and CLAUDE.md are out of sync from 'Project Overview' onward"
        )
    return failures


def _iter_nav_paths(node: object) -> list[str]:
    paths: list[str] = []
    if isinstance(node, list):
        for item in node:
            paths.extend(_iter_nav_paths(item))
    elif isinstance(node, dict):
        for value in node.values():
            paths.extend(_iter_nav_paths(value))
    elif isinstance(node, str) and node.endswith(".md"):
        paths.append(node)
    return paths


def _check_mkdocs_nav() -> list[str]:
    config = yaml.safe_load(MKDOCS_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []
    for rel_doc in _iter_nav_paths(config.get("nav", [])):
        path = REPO_ROOT / "docs" / rel_doc
        if not path.exists():
            failures.append(f"MkDocs nav points to missing file: docs/{rel_doc}")
    return failures


def main() -> int:
    failures = []
    tracked_files = _tracked_files()
    failures.extend(_check_required_files_exist())
    failures.extend(_check_required_files_not_ignored())
    failures.extend(_check_agent_guides_synced())
    failures.extend(_find_unexpected_placeholders(tracked_files))
    failures.extend(_check_mkdocs_nav())

    if failures:
        print("Template documentation checks failed:\n")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Template documentation checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
