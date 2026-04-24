# ADR-002: Tailwind CSS Only

## Status
Accepted

## Context
The template is designed for predictable AI-assisted development and low-friction
UI maintenance across small university software teams.

## Decision
Use Tailwind CSS utility classes only. Do not introduce CSS component libraries,
CSS modules, or ad hoc styling systems by default.

## Consequences
Styling stays consistent across projects and easier for both humans and coding
agents to extend. The tradeoff is more utility-class-heavy markup.
