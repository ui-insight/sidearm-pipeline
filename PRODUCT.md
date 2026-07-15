# Product

## Register

product

## Users

The primary users are University of Idaho Sports Information Directors and
athletics newsroom staff. They work under deadline, maintain authoritative
records, investigate player and team history, resolve data ambiguities, and turn
verified facts into publishable coverage. The first-release interface should
support newsroom operations and SID analytics exploration before fan-facing use.

## Product Purpose

Vandals Stats Pipeline is an internal athletics data warehouse and exploratory
workspace. It ingests source data, resolves identities, preserves provenance,
and makes trustworthy game and historical facts easy to inspect. Success means
an SID can move quickly from a game or data-quality issue to verified evidence,
understand uncertainty, and make a confident editorial decision without using
SQL or manually reconciling source pages.

## Brand Personality

Authoritative, focused, composed. The product should have the professional
editorial confidence of leading sports-news organizations such as ESPN and The
Athletic, adapted for an internal operations tool rather than a public media
property. Copy is direct, factual, and calm under pressure.

## Anti-references

- A fan-facing athletics site built around hype, promotional graphics, or game-day spectacle
- A generic SaaS dashboard made from interchangeable cards and decorative metrics
- A database administration console that exposes implementation details instead of newsroom concepts
- A chatbot-first interface that obscures evidence or treats generated prose as authoritative
- Sports-broadcast styling that sacrifices legibility, density, or provenance for visual drama

## Design Principles

1. **Lead with the editorial question.** Organize screens around the decisions an SID needs to make, not around database tables.
2. **Evidence stays attached.** Show provenance, coverage, and resolution state close to every fact that could be quoted or published.
3. **Dense, never cluttered.** Support rapid scanning and comparison with strong hierarchy, restrained decoration, and deliberate spacing.
4. **Uncertainty is actionable.** Ambiguous identities and source gaps should be visible, specific, and resolvable without guessing.
5. **Professional sports editorial, internally focused.** Use confident typography and disciplined data presentation without imitating a fan site.

## Accessibility & Inclusion

Target WCAG 2.2 AA. All core workflows must be keyboard accessible, use visible
focus states, retain meaning without color alone, and work with screen readers.
Respect reduced-motion preferences and avoid motion that is required to
understand state changes.
