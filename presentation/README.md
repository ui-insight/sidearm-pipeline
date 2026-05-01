# Launching-pad presentation

Single-file reveal.js deck served at the root of GitHub Pages
(`https://ui-insight.github.io/sidearm-pipeline/`). The MkDocs documentation
site lives at `/docs/` on the same host.

## Editing

Everything is in `index.html`:

- **Slides** are `<section>` elements inside `<div class="slides">`.
- **Palette and typography** are in the inline `<style>` block at the top.
  Pride Gold `#F1B300`, Brand Black `#191919`, Public Sans (variable, weight
  900 for headings). Match `AISPEG/.impeccable.md`.
- **Reveal.js** loads from jsDelivr — no build step.

To preview locally:

```bash
# any static server works
cd presentation
python -m http.server 8080
# open http://localhost:8080
```

## Conventions

- No title slide. No agenda slide. No "your turn" wrap-up.
- Owner names are rendered with `<i class="owner">…</i>` (italic + gold).
- Pride Gold is rare — used for emphasis on a single phrase per slide and
  for `gold-bullet` list items.
- Speaker register: declarative, evidence-forward. *Nature* article voice,
  not TechCrunch.

## Deployment

Pushed automatically by `.github/workflows/docs.yml` on changes to
`presentation/**`, `docs/**`, or `mkdocs.yml`. The workflow builds MkDocs
into `_publish/docs/`, copies `presentation/` into `_publish/`, and
publishes the combined tree to the `gh-pages` branch.
