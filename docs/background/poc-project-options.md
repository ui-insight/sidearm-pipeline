# PRP Intern POC Project Options

> Source document for the bootcamp project selection. Originally authored
> as a Word document; preserved here as repository documentation so the
> rationale for choosing this project lives alongside the code.

## Context and Purpose

This document presents two candidate POC projects for the 3–4 week bootcamp
that will prepare our interns for their work at Profit Recovery Partners
(PRP). Both projects are designed to give students balanced, hands-on
experience with:

- Model-agnostic AI agent workflows (Instructions / Memory / Skills / Heartbeat)
- Enterprise SDLC (Agile sprints, GitHub, Azure DevOps, CI/CD pipelines)
- Multi-model comparison (testing prompts against Anthropic Claude and OpenAI GPT)
- Markdown-native development (VS Code, `.md` folder structures, Copilot-assisted coding)
- Real stakeholder engagement (iteration with users who want the deliverable)

The POC topic is distinct from the PRP use cases (which will arrive via
Dan). The bootcamp project gives students the technical fluency and process
muscle memory so they can hit the ground running at PRP on the
NemoClaw/OpenClaw sandbox.

---

## Project 1 — Vandals Stats Pipeline (Athletics Event Data Agent)

### Overview

An agentic system that scrapes, normalizes, and serves University of Idaho
athletic event data from Sidearm Sports to the Vandal Athletics
(govandals.com). The agent ingests boxscore HTML (or better yet the vendor
API if it exists) across multiple sports, stores structured
game/stat/scoring-play data in PostgreSQL, generates AI-written recaps and
social posts, and provides a natural-language query interface so athletics
staff can ask questions like *"How did volleyball do in conference play
this season?"*

**Prototype status.** A working codebase exists with Sidearm HTML scrapers,
a normalized PostgreSQL schema (games, team stats, player stat groups,
scoring plays, ingest runs), an AI content-generation service using the
Anthropic SDK (model-agnostic via base URL swap), a React review UI,
Docker Compose deployment, and GitHub Actions CI. What remains is the
natural-language query interface, automated heartbeat scheduling, and
production deployment.

### Key assets

- **GitHub repository**: [`ui-insight/sidearm-pipeline`](https://github.com/ui-insight/sidearm-pipeline)
- **Source data**: govandals.com (public athletics pages; Sidearm data source needs further elaboration)
- **Template origin**: [`ui-insight/TEMPLATE-app`](https://github.com/ui-insight/TEMPLATE-app)

### Agent architecture mapping *(very provisional)*

| PRP concept    | Implementation                                                                                                         | What interns build                                                                       |
|----------------|------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| Instructions   | System prompt with AP-style house rules for content generation; governance rules in `AGENTS.md`                        | Formalize into canonical `Instructions.md`; add NLQ system prompt                        |
| Memory         | PostgreSQL with normalized game/stat schema; source snapshots for replay                                                | Extend schema for NLQ context; add conversation memory for follow-up queries             |
| Skills         | Sidearm scraper, schedule parser, content generator (headline, recap, social post)                                     | Add NLQ skill (text-to-SQL or RAG-over-DB); refactor each as standalone `.md` skill      |
| Heartbeat      | Polling policy in `source_registry.json` (pregame/live/postgame cadences per sport)                                    | Implement scheduler on cadence; add health checks and retry logic                        |

### Pros

- **Working prototype exists.** Interns fork a running system rather than starting from zero. Faster time-to-demo.
- **Public data, zero sensitivity risk.** All source data is on govandals.com. No FERPA, PII, or firewall concerns.
- **Model-agnostic by design.** Content generator already swaps between Claude and MindRouter (Llama/Qwen). Adding OpenAI is a one-line config change.
- **High demo impact.** A chatbot that answers *"Who scored the most touchdowns?"* or auto-generates game recaps is immediately impressive to any audience.
- **Extends AI into a new university domain.** Aligns with the institutional strategic plan to broaden AI integration beyond research administration / operations into athletics. Demonstrates breadth of capability and lets us learn nuances of another department.
- **Natural Azure DevOps fit.** As a university client project, the ultimate deployment and maintenance path fits cleanly into OIT's ADO pipeline and release management model.
- **Leverages team expertise.** Colin's RAG and invoice-extraction experience maps directly to the NLQ and structured-data layers.
- **Full-stack SDLC surface area.** Repo already has Git branching, CI/CD, Docker, Alembic migrations, typed API contracts, Playwright tests, and ADRs.
- **Genuine stakeholder.** Athletics has expressed strong interest in this tool.

### Cons

- **Client availability is limited.** Athletics is extremely busy — the iteration loop with the stakeholder may not be tight on a 3–4 week timeframe, even though they are interested in the longer term.
- **Scope creep from parser edge cases.** Five sports with structural differences (volleyball sets vs. football quarters) could pull interns into debugging scraper code rather than building the agentic layer PRP cares about. Maybe this is mitigated if Sidearm has an API (applies below as well).
- **Scraping fragility.** Sidearm can change HTML without notice. *Mitigation:* checked-in HTML fixtures so development is never blocked by a live site change.
- **NLQ layer is unbuilt and non-trivial.** Text-to-SQL or RAG-over-DB is a real engineering challenge. May need to use an established pattern rather than building from scratch.
- **Not yet on NemoClaw.** Porting from Docker/PostgreSQL to PRP's sandbox would need adaptation, though the containerized stack should map cleanly.

---

## Project 2 — AI4RA Project Intelligence Agent

### Overview

A multi-source agentic orchestrator that provides a single conversational
interface over the entire AI4RA initiative. Sources include the AI4RA
GitHub organization, the Vandalizer trial platform, the ai4ra.uidaho.edu
community of practice, strategic planning documents, and the team's
ClickUp project management workspace. A team member could ask *"Which
prompt-library components haven't been fully evaluated yet?"*, *"What
ClickUp tasks are blocked this sprint?"*, or *"What did we commit to in
the strategic plan about community engagement?"*

**Prototype status.** No unified agent exists yet. However, the underlying
sources are well-structured: the prompt library has 13 components with
machine-readable catalogs, the evaluation triad has formal contract
surfaces, the eCFR MCP server demonstrates the MCP integration pattern,
and ClickUp is already connected as an MCP tool.

### Key assets

**AI4RA GitHub organization**

- `AI4RA/prompt-library` — 13 versioned components, 3 workflows, machine-readable `component_catalog.json`
- `AI4RA/evaluation-data-sets` — datasets, artifacts, and scoring references with `dataset_catalog.json`
- `AI4RA/evaluation-harness` — execution, provenance capture, run artifacts with `harness_catalog.json`
- `AI4RA/mcp-ecfr` — eCFR MCP server (Claude connector for federal regulations)
- `AI4RA/.github` — org governance: `CODE_OF_CONDUCT`, `CONTRIBUTING`, `SECURITY`, `SUPPORT`

**Shared data model**

- `ui-insight/AI4RA-UDM` — shared UDM foundation used across prompt-library components

**Platforms and tools**

- **Vandalizer**: vandalizer.uidaho.edu — trial workflow platform with exported `.vandalizer.json` manifests
- **Community of Practice**: ai4ra.uidaho.edu — website, newsletters, community engagement
- **Project management**: ClickUp workspace (MCP connector available)
- **NSF award**: NSF 2427549

### Agent architecture mapping *(very provisional)*

| PRP concept    | Implementation                                                                                                          | What interns build                                                                                       |
|----------------|-------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| Instructions   | AI4RA governance: triad pattern, repo boundaries (AI4RA vs. ui-insight), versioning and evaluation posture rules         | Author `Instructions.md` encoding governance rules so the agent reasons correctly about component relationships |
| Memory         | Cross-source index linking components to ClickUp tasks, eval datasets to prompts, strategic plan goals to milestones     | Design and build a relationship graph or structured index that persists between sessions                 |
| Skills         | GitHub skill (repos, issues, PRs), ClickUp skill (tasks, sprints), Document skill (RAG over PDFs), Catalog skill (`component_catalog.json`) | Implement 2–3 skills as standalone `.md` modules; wire routing logic to dispatch queries                 |
| Heartbeat      | Periodic sync pulling fresh data from GitHub and ClickUp to keep the memory index current                                | Build scheduled sync loop with staleness detection and incremental update logic                          |

### Pros

- **Teaches multi-source orchestration.** The real-world pattern PRP needs: an agent that routes across multiple data sources, resolves cross-references, and synthesizes answers beyond just single-source RAG.
- **Directly practices PRP's native idiom.** The prompt library already uses `prompt.md` / `SKILL.md` / `AGENT.md` / `schema.json`. Interns build inside an ecosystem that is intentionally growing in that direction the pattern at scale (13 components, 3 workflows).
- **Tight iteration loop with stakeholder.** Barrie is embedded in the AI4RA project and can provide rapid feedback, review demos, and adjust priorities within the sprint cycle — potentially leading to less potential scheduling conflicts with a busy external client.
- **Closer match to PRP's data structure.** Multiple structured catalogs, cross-referencing metadata, machine-readable contracts, and project management integration closely mirrors the enterprise audit-recovery environment at PRP.
- **ClickUp integration provides real SDLC texture.** Instead of simulating project management, interns integrate with the actual tool the team uses — reading real sprint data, task statuses, and blockers.
- **Machine-readable catalogs already exist.** `component_catalog.json`, `harness_catalog.json`, and `dataset_catalog.json` are purpose-built discovery surfaces. Interns build the consumer, not the data model.
- **Model comparison is the library's native use case.** Prompt-library components are explicitly LLM-agnostic. Running the same prompt against Claude and GPT is the library's intended workflow.
- **Strong institutional narrative.** Interns building tooling for an NSF-funded, presidential-priority initiative makes a compelling story for the repeatable internship program.

### Cons

- **Larger scope with no existing prototype.** Four to five data sources and no running codebase. Requires tighter scope management. Probably start with GitHub + component catalog, add ClickUp in Sprint 2, treat document RAG as a stretch goal.
- **Higher abstraction level.** This is meta-work that involves building a tool to manage the tools. Interns may need a longer orientation to understand what prompt-library components do before they can build an agent that reasons about them.
- **Azure DevOps is a clumsy fit.** AI4RA uses GitHub natively and does not use ADO. Adding ADO Repos/Test Plans/Pipelines for the bootcamp would feel artificial rather than organic to the project's actual workflow.
- **Connector reliability.** The ClickUp MCP connector can be flaky. Debugging integration timeouts is a real enterprise skill but can burn an entire day. *Mitigation:* cached/snapshot fallback.
- **Slightly higher data sensitivity.** Strategic plan PDFs and ClickUp workspace contain internal university planning data. Not confidential, but interns need to understand data classification before adding internal sources.

---

## Side-by-side comparison

| Dimension                | Athletics (Project 1)                                              | AI4RA (Project 2)                                                       |
|--------------------------|--------------------------------------------------------------------|-------------------------------------------------------------------------|
| Starting point           | Working prototype with scraper, DB, content gen, CI/CD              | Rich structured sources but no unified agent codebase                   |
| Data sources             | Single source (Sidearm HTML)                                        | 4–5 sources (GitHub, ClickUp, Vandalizer, docs, website)                |
| Data sensitivity         | All public                                                          | Mostly public; some internal planning docs                              |
| Agent complexity         | Single-domain pipeline + NLQ                                        | Multi-source orchestration + routing                                    |
| ADO pipeline fit         | Natural — university client, OIT deployment path                    | Forced — AI4RA is GitHub-native, doesn't use ADO                        |
| Client iteration speed   | Slower — Athletics is busy, scheduling is harder                    | Faster — Barrie controls cadence directly                               |
| Closeness to PRP work    | Good — pipeline + content gen + NLQ                                 | Better — multi-source, structured catalogs, PM integration              |
| Demo impact              | High — sports content is universally engaging                       | Medium — impressive to technical audience                               |
| Strategic alignment      | Extends AI to new university domain                                 | Strengthens existing NSF-funded initiative                              |
| Risk of not finishing    | Lower — prototype de-risks the build                                | Higher — more greenfield, needs strict scope control                    |
| Team expertise           | RAG + structured extraction experience                              | Prompt engineering + eval + MCP experience                              |

---

## Options for Discussion

These projects are not mutually exclusive. Depending on how many interns
we have and how we want to structure the bootcamp, several configurations
are possible:

1. **One project, both interns (paired).** Simpler to manage. Athletics is
   the safer bet for landing a demo in 3–4 weeks. AI4RA is the
   higher-ceiling option if we're comfortable with more scope management.
   *(This is Barrie's vote.)*
2. **One intern per project (parallel).** Covers more ground. Athletics
   teaches end-to-end pipeline + content generation. AI4RA teaches
   multi-source orchestration + tool integration. Both map to PRP's
   framework but emphasize different facets. Requires more mentorship
   bandwidth.
3. **Sequential (Athletics first, then AI4RA).** If the bootcamp is closer
   to 5–6 weeks, start with Athletics (quicker wins, existing prototype)
   then transition to AI4RA for the multi-source orchestration layer.
   Deepest learning, but longest timeline. *(Very unlikely on our
   timeframe.)*

---

## Open Questions

- **POC selection**: one project or two? If one, which?
- Do PRP's technical docs (arriving from Dan) change the calculus on which project is closer to their use cases?
- **ADO requirement**: is ADO experience a hard requirement from PRP, or can we satisfy it with a lighter-touch integration (e.g., mirroring GitHub PRs to ADO Test Plans)?
- **Athletics contact**: who is our primary liaison, and can we get one requirements session on the calendar regardless of which project we pick?

---

## Outcome

Project 1 — the Vandals Stats Pipeline — was selected as the bootcamp's
first formal foray into agentic systems for IIDS. Project 2 (the AI4RA
Project Intelligence Agent) is held as the second foray.

The candidate scoping moves for laying the agentic foundation in this
repository are tracked in
[Epic #61](https://github.com/ui-insight/sidearm-pipeline/issues/61).
