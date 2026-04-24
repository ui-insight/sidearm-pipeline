#!/usr/bin/env python3
"""Apply first-run template customization to this repository."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from check_template_docs import CUSTOMIZABLE_PROJECT_NAME_FILES

REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = Path("README.md")
GETTING_STARTED_PATH = Path("docs/contributing/getting-started.md")
AGENT_GUIDE_PATHS = (Path("CLAUDE.md"), Path("AGENTS.md"))


def slugify(value: str) -> str:
    """Convert display text into a repository-friendly slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip()).strip("-").lower()
    return slug or "app"


def infer_origin_metadata(repo_root: Path) -> tuple[str | None, str | None]:
    """Infer repo owner and name from the origin remote when available."""
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None, None

    remote = result.stdout.strip()
    if not remote:
        return None, None

    if remote.endswith(".git"):
        remote = remote[:-4]
    if remote.startswith("git@") and ":" in remote:
        remote = remote.split(":", maxsplit=1)[1]
    elif "://" in remote:
        remote = remote.split("://", maxsplit=1)[1]
        if "/" in remote:
            remote = remote.split("/", maxsplit=1)[1]

    parts = [part for part in remote.split("/") if part]
    if len(parts) < 2:
        return None, None

    return parts[-2], parts[-1]


def update_file(
    repo_root: Path,
    rel_path: Path,
    transform: Callable[[str], str],
) -> bool:
    """Apply a text transform to a file and write it back if it changed."""
    abs_path = repo_root / rel_path
    original = abs_path.read_text(encoding="utf-8")
    updated = transform(original)
    if updated == original:
        return False
    abs_path.write_text(updated, encoding="utf-8")
    return True


def replace_project_name(repo_root: Path, project_name: str) -> list[Path]:
    """Replace project-name placeholders in the standard customization files."""
    updated_paths: list[Path] = []
    for rel_path in sorted(CUSTOMIZABLE_PROJECT_NAME_FILES, key=str):
        changed = update_file(
            repo_root,
            rel_path,
            lambda text, project_name=project_name: text.replace(
                "{{PROJECT_NAME}}",
                project_name,
            ),
        )
        if changed:
            updated_paths.append(rel_path)
    return updated_paths


def update_agent_guides(
    repo_root: Path,
    description: str | None,
    status: str | None,
) -> list[Path]:
    """Fill in optional project metadata in CLAUDE.md and AGENTS.md."""
    updated_paths: list[Path] = []
    replacements = {
        r"^\*\*Description\*\*: .*$": (
            f"**Description**: {description}" if description else None
        ),
        r"^\*\*Status\*\*: .*$": f"**Status**: {status}" if status else None,
    }

    for rel_path in AGENT_GUIDE_PATHS:
        def transform(text: str, replacements: dict[str, str | None] = replacements) -> str:
            updated = text
            for pattern, replacement in replacements.items():
                if replacement is None:
                    continue
                updated = re.sub(pattern, replacement, updated, flags=re.MULTILINE)
            return updated

        if update_file(repo_root, rel_path, transform):
            updated_paths.append(rel_path)

    return updated_paths


def update_readme_description(repo_root: Path, description: str | None) -> list[Path]:
    """Replace the README placeholder description blockquote."""
    if not description:
        return []

    pattern = re.compile(
        r"(^> \*\*This repository was created from .*\n)(> .*$)",
        flags=re.MULTILINE,
    )

    def transform(text: str) -> str:
        return pattern.sub(rf"\1> {description}", text, count=1)

    return [README_PATH] if update_file(repo_root, README_PATH, transform) else []


def update_clone_commands(
    repo_root: Path,
    repo_owner: str,
    repo_name: str,
) -> list[Path]:
    """Update the clone/cd example in the getting-started guide."""
    block_pattern = re.compile(
        r"(### 1\. Clone the Repository\n\n```bash\n)"
        r"(?P<clone>git clone [^\n]+)\n"
        r"(?P<cd>cd [^\n]+)\n```",
        flags=re.MULTILINE,
    )

    def transform(text: str) -> str:
        replacement = (
            r"\1"
            f"git clone https://github.com/{repo_owner}/{repo_name}.git\n"
            f"cd {repo_name}\n"
            "```"
        )
        return block_pattern.sub(replacement, text, count=1)

    return (
        [GETTING_STARTED_PATH]
        if update_file(repo_root, GETTING_STARTED_PATH, transform)
        else []
    )


def run_docs_check(repo_root: Path) -> None:
    """Run the existing template docs integrity check after customization."""
    subprocess.run(
        [sys.executable, str(repo_root / "scripts/check_template_docs.py")],
        cwd=repo_root,
        check=True,
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Customize TEMPLATE-app metadata in this repository.",
    )
    parser.add_argument("project_name", help="Display name for the project")
    parser.add_argument(
        "--description",
        help="Short project description for README and agent guides",
    )
    parser.add_argument(
        "--status",
        choices=["planning", "in development", "alpha", "beta", "production"],
        help="Project status value for CLAUDE.md and AGENTS.md",
    )
    parser.add_argument(
        "--repo-owner",
        help="GitHub owner or organization for clone examples",
    )
    parser.add_argument(
        "--repo-name",
        help="Repository name for clone examples (defaults to origin remote or slugified project name)",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root to customize (advanced use)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    if not repo_root.exists():
        print(f"Repository root does not exist: {repo_root}", file=sys.stderr)
        return 1

    inferred_owner, inferred_name = infer_origin_metadata(repo_root)
    repo_owner = args.repo_owner or inferred_owner
    repo_name = args.repo_name or inferred_name or slugify(args.project_name)

    updated_paths = set(replace_project_name(repo_root, args.project_name))
    updated_paths.update(update_agent_guides(repo_root, args.description, args.status))
    updated_paths.update(update_readme_description(repo_root, args.description))
    if repo_owner:
        updated_paths.update(update_clone_commands(repo_root, repo_owner, repo_name))

    run_docs_check(repo_root)

    print("Customization complete.")
    if updated_paths:
        print("\nUpdated files:")
        for rel_path in sorted(updated_paths, key=str):
            print(f"- {rel_path}")
    else:
        print("\nNo files changed.")

    print("\nReview these remaining project-specific items before shipping:")
    print("- .github/CODEOWNERS")
    print("- SECURITY.md")
    print("- deployment and hosting settings")
    if not args.description or not args.status:
        print("- README.md, CLAUDE.md, and AGENTS.md metadata")
    if not repo_owner:
        print("- docs/contributing/getting-started.md clone URL")

    return 0


if __name__ == "__main__":
    sys.exit(main())
