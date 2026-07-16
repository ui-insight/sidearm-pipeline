# Onboarding — read this first

If you are a new contributor (intern or otherwise), this doc points you
through the existing files in the order they make sense. None of the
content below is duplicated here; this is the reading path, not the
material itself.

If you hit a term you don't recognize, check the
[Glossary](glossary.md).

---

## Hour 1 — what is this and why

1. **[README.md](https://github.com/ui-insight/sidearm-pipeline/blob/main/README.md)**
   — what this project is, the tech stack, and the quick start. Skim only;
   you will return to it.
2. **[Background — POC Project Options](background/poc-project-options.md)**
   — why this project was chosen for the bootcamp, what the alternative
   was, and what the trade-offs looked like. Read in full.
3. **[Architecture Overview](architecture/overview.md)** — the system at
   one zoom level. Look at the diagram and the design principles; come
   back later for details.

By the end of this hour you should be able to answer, in your own
words: *what does this app do, and why this app for the bootcamp?*

---

## Hour 2 — set up local dev

4. **[Contributing — Getting Started](contributing/getting-started.md)**
   — the actual `make setup` / Postgres / backend / frontend recipe.
   Follow it end to end. When `make check-all` is green, your environment
   is good.

If something fails here, *flag it before you keep going.* Day-one
environment problems compound.

---

## Hour 3 — internalize the rules

5. **[CLAUDE.md](https://github.com/ui-insight/sidearm-pipeline/blob/main/CLAUDE.md)**
   (or its synchronized twin `AGENTS.md`) — the canonical guide for
   anyone — human or agent — working in this repo. The *Never Do* and
   *Always Do* lists are normative. Read them carefully. The same file
   briefs the agent and briefs you.
6. **[Architecture Decision Records](adr/index.md)** — every non-obvious
   decision in the codebase has a short ADR. Read the index and any ADRs
   referenced by the current implementation plan.
7. **[Data Classification](governance/data-classification.md)** — before
   you store or expose data, classify it. The matrix on this page is the
   rulebook.

By the end of this hour you should know what you are *not* allowed to do.

---

## Hour 4 — see what's open

8. **[Reboot Implementation Plan](architecture/reboot-implementation-plan.md)**
   — the current source-to-warehouse-to-exploration sequence, Release 1
   acceptance gates, sport-expansion cohorts, and first-day checklist.
9. **[Epic #81 — WBB athletics data warehouse and internal SID tool](https://github.com/ui-insight/sidearm-pipeline/issues/81)**
   — the current Release 1 backlog. Compare its child issues against the
   revised plan before starting implementation; backlog alignment is the
   first project-management task.
10. **[Open issues](https://github.com/ui-insight/sidearm-pipeline/issues)**
    — the broader backlog.

By the end of this hour you should be able to point at a specific
piece of work and say *"this is what I'd start on, and this is why."*

---

## When you get stuck

- **External tools and skill collections**: see
  [Resources](resources.md) — MindRouter,
  `mattpocock/skills`, `pbakaus/impeccable`.
- **Project-specific terms**: see [Glossary](glossary.md).
- **A pattern is unclear**: search the codebase first. The repo is the
  source of truth — if you cannot find an answer in code or docs, that
  is the moment to ask a human.

---

## Conventions you will run into immediately

- All work happens on a feature branch (`feature/...`, `fix/...`,
  `docs/...`). Direct commits to `main` are not allowed.
- AI-assisted commits include a `Co-Authored-By` trailer naming the
  agent — see `CLAUDE.md` rule 13.
- Tests must pass locally before you claim a task is done. CI is the
  gate, but it is not your *first* check; `make check-all` is.
- If a decision is non-obvious, write an ADR. *Three similar lines is
  better than a premature abstraction* (`AGENTS.md` rule 8) — but a
  decision worth re-asking later is worth recording.

If you have read this far, you are oriented. Start at hour 2.
