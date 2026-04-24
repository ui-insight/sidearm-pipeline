# ADR-001: Preserve Explicit Template Customization Points

## Status
Accepted

## Context
This repository is intentionally used as a scaffold for new projects. Some files
need obvious, mechanical customization on day one, especially project naming,
repository URLs, and security ownership metadata.

## Decision
Keep `{{PROJECT_NAME}}` placeholders only in a small, documented set of files and
add automation to detect any unexpected template placeholders elsewhere.

## Consequences
Template consumers get clear first-run customization cues without accidental
placeholder leakage into unrelated files.
