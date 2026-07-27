# Glossary

Project-specific and domain-specific terms used in this repo's docs.
General CS vocabulary (CORS, JWT, async/await, etc.) is intentionally
omitted — those are findable. The terms below are the ones a new
contributor will hit and not be sure about.

---

## Athletics domain

**Boxscore** — the post-game statistical summary for a single contest:
final score, team stats, player stats, scoring plays. The primary unit
of source data this pipeline ingests.

**Sidearm** — the third-party platform (Sidearm Sports) that powers
[govandals.com](https://govandals.com). Boxscores are scraped or
otherwise fetched from Sidearm-rendered pages.

**Schedule** — the season calendar for a given sport. Comes from
Sidearm separately from boxscores. Used to discover upcoming games and
to backfill historical contests.

**Recap** — an optional AI-generated editorial draft derived from a stored game.
It remains Internal until a human publication decision; it is not a warehouse fact.

**Conference event** — a game between teams in the same athletic
conference. Affects standings differently than non-conference play.

---

## Agentic concepts

**Agent** — an LLM-powered process that reads a prompt, optionally
calls tools, and produces a structured output. In this repo, an agent
is owned by a module (e.g., a recap-writer agent), not by a single
prompt invocation.

**AI-assisted surface** — a place where a configured model may assist without
becoming authoritative. Current surfaces are generated editorial drafts,
Achievement Suggestion ranking/phrasing, and natural-language mapping/phrasing
over the semantic catalog. Scheduled ingestion is deterministic orchestration,
not an LLM responsibility, and is not currently implemented as a persisted job.

**Agentic loop** — the cycle that produces and validates an agent's
work: read instructions → propose output → human review → persist (or
reject). Distinct from a one-shot LLM call.

**Instructions / Memory / Skills / Heartbeat** — the four-element
pattern this repo uses to describe agentic systems. *Instructions* are
the constraints the agent reads first (`AGENTS.md`, ADRs, prompts).
*Memory* is the persistent state (DB rows, run history, accepted/rejected
verdicts). *Skills* are composable, single-task `SKILL.md` modules.
*Heartbeat* is scheduled, autonomous action — the agent operating
without being prompted.

**NLQ / Ask-a-Question** — a natural-language interface that maps a supported SID
question onto a human-authored semantic query and lets the warehouse compute the
answer. It is implemented for the curated catalog and explicitly is not free
text-to-SQL; unsupported questions fail honestly.

**Model-agnostic** — the claim that swapping the LLM provider does not
require code changes. In this repo, the content-generation service uses
the Anthropic SDK with a configurable base URL; one environment
variable points at Claude, MindRouter, or an OpenAI-compatible endpoint.

**Provenance** — evidence that explains a result. Warehouse facts reference
source snapshots; AI-ranked Achievement Suggestions retain model, prompt
version, output hash, ranking time, and current SID review provenance. There is
not yet one generalized immutable agent/operator-run audit table.

**LLM-as-editor** — a pattern where an LLM proposes a change to a
document and a human reviews the diff before persistence. Pioneered in
this codebase's reference set by the UCM Daily Register.

**Eval / evaluation harness** — automated testing of prompts. Inputs,
expected outputs, and a metric (exact match, similarity, LLM-as-judge)
that lets CI catch a prompt regression. See
[Issue #59](https://github.com/ui-insight/sidearm-pipeline/issues/59).

---

## Repo and process

**ADR** — Architecture Decision Record. A short markdown file in
`docs/adr/` capturing context, decision, and consequences for a
non-obvious choice. Numbered sequentially.

**`AGENTS.md` / `CLAUDE.md`** — the canonical agent guide for this
project. The two files are kept synchronized; `CLAUDE.md` is the
tracked source of truth and `AGENTS.md` is the synchronized twin for
toolchains that read that name.

**TEMPLATE-app** — the IIDS-maintained starter template
([`ui-insight/TEMPLATE-app`](https://github.com/ui-insight/TEMPLATE-app))
that this repo was bootstrapped from. Patterns here largely come from
that template.

**MindRouter** — IIDS's institutional LLM inference load balancer. See
[Resources](resources.md). Fronts an on-prem Ollama + vLLM cluster and
exposes OpenAI-, Anthropic-, and Ollama-compatible endpoints.

**Ingest run** — one execution or parent checkpoint for an ingest/backfill
operation. Each run records source/range context, status, timing, retry attempts,
structured metadata, and any error in `ingest_runs`.

**Canonical event / canonical UID** — the project's stable identifier
for a single contest, independent of how the source numbers it.
Lets repeat ingests of the same game update the existing record
instead of creating duplicates.

**Co-Authored-By** — a Git commit trailer that names another author.
This repo's `CLAUDE.md` rule 13 requires AI-assisted commits to
include the agent's name as a co-author.

**MkDocs strict** — `mkdocs build --strict` fails on broken nav links,
missing pages, or other doc-structure issues. Runs on every PR via
the `Documentation Check` workflow.

**`make check-all`** — the umbrella target that runs backend tests,
frontend tests, e2e smoke, docs check, and dependency-policy checks
in one command. The local equivalent of CI.

**SBOM** — Software Bill of Materials. A machine-readable list of
every dependency. Generated automatically per PR by `sbom.yml` for
backend and frontend; lives as a workflow artifact.

---

## Acronyms used elsewhere

**FERPA** — Family Educational Rights and Privacy Act. The U.S. law
that restricts how student educational records may be shared. Public
athletics data on `govandals.com` is *not* FERPA-protected, which is a
deliberate reason this project was chosen as a low-risk first foray.

**PRP** — Profit Recovery Partners, the external partner the interns
will work with after the bootcamp. The bootcamp project (this repo) is
intentionally distinct from the PRP use cases — see
[Background — POC Project Options](background/poc-project-options.md).

**IIDS** — Institute for Interdisciplinary Data Sciences at the
University of Idaho. The team that owns this repo and the broader
agentic-development practice it sits in.

**OIT** — Office of Information Technology at the University of Idaho.
The institutional IT organization. Distinct from IIDS.

**NSF GRANTED** — the National Science Foundation's
[GRANTED program](https://new.nsf.gov/granted), which funds research
administration capacity-building. AI4RA, the partnership that produces
some of the tools referenced here (Vandalizer, MindRouter), is funded
under NSF GRANTED Award #2427549.
