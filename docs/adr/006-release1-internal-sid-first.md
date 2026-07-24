# 006 — Release 1 is internal-SID-first; public website deferred to Release 2

**Status:** accepted — supersedes the roadmap framing that placed website
syndication/display (core-functionality-roadmap Phases 5–6, epic-drafts Epics 5–6)
in Release 1.

## Decision

Release 1 delivers an **internal tool for the Sports Information Director (SID)** —
game review with ranked Achievement Suggestions, Ask-a-Question over the semantic
layer, and Record Book / leaders views — over the athletics data warehouse. It does
**not** ship any fan-facing output on govandals.com. Public website syndication and
display move to Release 2.

## Context

Website delivery cannot be built until the **integration mode** (API pull vs.
embedded widgets vs. shared components) is chosen, and that decision belongs to the
athletics web team and is not yet made. Making the public website a Release 1 gate
would block the entire reboot on an external decision outside our control.
Meanwhile the SID is the primary user, and the warehouse's records/achievements value
stands on its own without a public surface.

## Consequences

- **Fans see nothing in Release 1** — every Release 1 surface is staff-facing. Accepted.
- The warehouse is proven by real SID usage before any fan depends on it.
- Release 2 (website) becomes low-risk: it exposes a warehouse that already exists and
  is trusted, and starts the moment the web team picks an integration mode.
