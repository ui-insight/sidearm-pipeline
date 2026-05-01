# Resources

Tools, skill collections, and references the bootcamp builds on.

## MindRouter

**[github.com/ui-insight/MindRouter](https://github.com/ui-insight/MindRouter)** — open-source
LLM inference load balancer fronting an on-prem Ollama + vLLM cluster at the
University of Idaho. Provides unified OpenAI-, Ollama-, and Anthropic-compatible
endpoints with fair-share scheduling, quotas, telemetry, Azure AD SSO, and full
audit logging. Deployed at UI; open-sourced at
**[mindrouter.ai](https://mindrouter.ai)**.

Why it matters here: every AI app at UI routes through MindRouter, so
"model-agnostic" is operational rather than aspirational. The same endpoint
shape as Anthropic means this pipeline can swap providers with one
environment-variable change.

Operational owner: Luke Sheneman, IIDS.

## mattpocock/skills

**[github.com/mattpocock/skills](https://github.com/mattpocock/skills)** — Matt
Pocock's public collection of Claude Code skills, drawn directly from his
`.claude` directory. Organized into:

- `engineering/` — coding-focused skills
- `productivity/` — workflow and agent-orchestration skills
- `personal/` — personal-knowledge and writing skills
- `misc/` — everything else

Self-described as "Skills for Real Engineers." A good orientation to how a
working engineer organizes Claude skills as a usable, daily toolkit rather than
a demo collection.

## pbakaus/impeccable

**[github.com/pbakaus/impeccable](https://github.com/pbakaus/impeccable)** — a
design-language skill family ("the design language that makes your AI harness
better at design"). Provides a set of skills — `impeccable`, `craft`, `teach`,
`extract`, plus design-discipline skills like `adapt`, `animate`, `audit`,
`bolder`, `clarify`, `colorize`, `critique`, `delight`, `distill`, `layout`,
`optimize` — that produce distinctive, production-grade frontend interfaces and
guard against generic "AI slop" aesthetics.

The impeccable family expects a project-level `.impeccable.md` file that
captures audience, use cases, and brand personality. Without that context the
skills will refuse to design and prompt for it instead — which is the point.
