# Claude Support Files

This directory is for optional, tool-specific helper files used during local
 development.

## What Belongs Here

- `settings.local.json` for machine-specific Claude/Codex permissions or local
  preferences
- optional local launch helpers that are specific to one contributor's machine

## What Does Not Belong Here

- canonical project rules
- repository-wide architecture or workflow guidance
- secrets or credentials

The maintained source of truth for tracked agent guidance in this repository is
[`CLAUDE.md`](../CLAUDE.md).

If you generate an `AGENTS.md` file for another tool or workflow, treat it as a
derived copy of `CLAUDE.md` unless your project explicitly chooses to track and
maintain both.
