# Agent Coordination Guide

This guide defines how AI coding agents collaborate on this project alongside human developers.

## Agent Identity and Attribution

All AI-assisted work must be properly attributed:

- **Commits**: include `Co-Authored-By: [Agent Name] <noreply@anthropic.com>` trailer
- **Pull Requests**: label with `ai-assisted` and fill in the Agent Context section of the PR template
- **Code comments**: do not add "AI-generated" comments — the git history provides attribution
- **Source of truth**: keep tracked project guidance centered in `CLAUDE.md`; any tool-specific helper files should defer to it
- **Derived files**: if a workflow also uses `AGENTS.md`, keep it generated or manually synced from `CLAUDE.md` rather than maintaining conflicting instructions

## Scope Boundaries

### Agents May Autonomously:
- Add new files within established patterns (new models, schemas, routes, components)
- Write and run tests
- Fix lint and type errors
- Update documentation for changes they made
- Create feature branches

### Agents Must Ask Before:
- Changing project structure or adding new top-level directories
- Adding new dependencies
- Modifying authentication or authorization logic
- Changing database schema in ways that affect existing data
- Modifying CI/CD workflows
- Deleting files or removing features

### Agents Must Never:
- Push directly to `main`
- Modify `.env` files (update `.env.example` and instruct the user)
- Commit secrets or credentials
- Make unsolicited improvements outside the requested scope
- Add unnecessary abstractions or "improvements"

## Intentional Design Choices

Some patterns in the codebase are intentional and should not be "fixed":

| Pattern | Reason |
|---|---|
| Tailwind classes only (no CSS library) | ADR-002: consistency and agent-friendliness |
| Thin route handlers | Business logic belongs in services |
| One file per resource | Predictable structure for agents and humans |
| PostgreSQL as the app default | Matches institutional deployment expectations and avoids local/prod drift |

## Conflict Prevention

- Always work on feature branches
- Coordinate at the file level — avoid multiple agents editing the same file simultaneously
- When in doubt about scope, ask the human orchestrator
- Pull latest changes before starting work
- Treat `.claude/settings.local.json` and similar local helper files as personal workstation state, not shared project policy

## Decision Escalation

**Proceed if**:
- The task is clearly defined and within scope boundaries
- You can follow existing patterns
- Tests pass after your changes

**Stop and ask if**:
- Requirements are ambiguous
- Multiple valid approaches exist and the choice matters
- Your changes would affect other developers' work
- You discover a bug or inconsistency unrelated to your task

## Reference

For a comprehensive agent coordination framework, see:
[OpenERA Agent Coordination](https://github.com/ui-insight/OpenERA/blob/main/docs/integration/agent-coordination.md)
