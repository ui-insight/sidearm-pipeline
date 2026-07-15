---
name: Vandals Stats Pipeline
description: An authoritative sports desk for verified Idaho athletics data.
colors:
  vandal-gold: "#eab308"
  vandal-gold-hover: "#ca8a04"
  editorial-ink: "#111827"
  newsroom-slate: "#374151"
  secondary-copy: "#6b7280"
  quiet-copy: "#9ca3af"
  newsroom-rule: "#e5e7eb"
  paper: "#ffffff"
  newsprint: "#f9fafb"
  alert-red: "#b91c1c"
  verified-green: "#166534"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, system-ui, sans-serif"
    fontSize: "32px"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.015em"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.35
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "0.06em"
rounded:
  sm: "4px"
  md: "6px"
  lg: "8px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  2xl: "32px"
  3xl: "40px"
components:
  button-primary:
    backgroundColor: "{colors.editorial-ink}"
    textColor: "{colors.paper}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-primary-hover:
    backgroundColor: "{colors.newsroom-slate}"
    textColor: "{colors.paper}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-accent:
    backgroundColor: "{colors.vandal-gold}"
    textColor: "{colors.editorial-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.editorial-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.editorial-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  status-chip:
    backgroundColor: "{colors.newsprint}"
    textColor: "{colors.secondary-copy}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: "2px 8px"
---

# Design System: Vandals Stats Pipeline

## 1. Overview

**Creative North Star: "The Sports Desk"**

The interface should feel like the working desk behind a trusted athletics publication: compact, evidence-rich, and composed under deadline. Strong typographic hierarchy separates the game, the fact, and the source without turning routine operations into spectacle. Familiar navigation, tables, filters, and forms should disappear into the editorial task.

This is an internal operations product, so density is useful when structure stays clear. Newsprint backgrounds, paper work surfaces, dark editorial ink, and a limited Vandal Gold accent create the professional confidence of ESPN or The Athletic without copying a fan-facing broadcast package. The system rejects promotional hype, interchangeable SaaS cards, exposed database concepts, chatbot-first ambiguity, and visual drama that compromises provenance or legibility.

**Key Characteristics:**

- Editorial hierarchy with compact, repeatable data rhythms
- Paper and newsprint surfaces separated by rules more often than shadows
- Vandal Gold reserved for primary actions, active state, and important attention
- Tabular numerals and aligned columns for fast comparison
- Evidence, uncertainty, and resolution state kept beside the fact

## 2. Colors

The palette pairs quiet newsroom neutrals with one controlled Idaho-gold signal.

### Primary

- **Vandal Gold** (#eab308): Primary ingest actions, active navigation, selected filters, and high-value attention states.
- **Deep Vandal Gold** (#ca8a04): Hover and active treatment for the gold accent.

### Neutral

- **Editorial Ink** (#111827): Primary copy, dark buttons, and the strongest structural emphasis.
- **Newsroom Slate** (#374151): Secondary dark controls and dense supporting copy.
- **Secondary Copy** (#6b7280): Metadata, field help, and less prominent labels.
- **Quiet Copy** (#9ca3af): Disabled or genuinely low-priority content only.
- **Newsroom Rule** (#e5e7eb): Dividers, table rules, and input borders.
- **Paper** (#ffffff): Working surfaces and controls.
- **Newsprint** (#f9fafb): Page canvas and secondary surface bands.
- **Alert Red** (#b91c1c): Destructive actions and errors, always paired with text or an icon.
- **Verified Green** (#166534): Successful imports and verified states, always paired with text or an icon.

### Named Rules

**The One Signal Rule.** Vandal Gold should occupy no more than roughly 10% of a screen. Its rarity gives it editorial authority.

**The Evidence Is Not Decoration Rule.** Red and green communicate status only; neither color may be used as ambient decoration, and neither may carry meaning alone.

## 3. Typography

**Display Font:** System UI (-apple-system, BlinkMacSystemFont, Segoe UI fallback)
**Body Font:** System UI (-apple-system, BlinkMacSystemFont, Segoe UI fallback)
**Label/Mono Font:** System UI for labels; ui-monospace for scores, timestamps, hashes, and dense statistics

**Character:** One native sans family keeps the operations surface familiar and fast. Weight, spacing, alignment, and tabular numerals create the sports-editorial character rather than an ornamental display face.

### Hierarchy

- **Display** (700, 32px, 1.15): Product and major workspace headings only.
- **Headline** (700, 24px, 1.2): Game titles and primary page questions.
- **Title** (600, 18px, 1.35): Section titles and table groups.
- **Body** (400, 14px, 1.5): Interface copy and table content; explanatory prose should stay near 70 characters per line.
- **Label** (600, 12px, 0.06em, uppercase): Column headings, compact metadata, and state vocabulary.

### Named Rules

**The Scoreboard Rhythm Rule.** Numerical comparisons use tabular numerals and right alignment; names and editorial context remain left aligned.

## 4. Elevation

The system is flat by default. Newsprint, Paper, and Newsroom Rule establish hierarchy through tonal layering and clean dividers. A single low ambient shadow (`0 1px 2px 0 rgb(0 0 0 / 0.05)`) is permitted for a contained work surface when a border alone does not separate it from the canvas; dialogs may earn stronger elevation when introduced.

### Shadow Vocabulary

- **Ambient Low** (`box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05)`): Large working surfaces on the newsprint canvas only.

### Named Rules

**The Flat-By-Default Rule.** Tables, filters, and repeated rows use rules and tonal contrast, not stacks of floating cards.

## 5. Components

Components are refined and restrained, with standard affordances and compact newsroom density.

### Buttons

- **Shape:** Compact rounded rectangle (6px) with 8px vertical and 16px horizontal padding.
- **Primary:** Editorial Ink background with Paper text for consequential workspace actions; Vandal Gold with Editorial Ink text for ingest and selected task actions.
- **Hover / Focus:** A 150ms color transition and a visible 2px Vandal Gold focus ring with 2px offset. Active state darkens one step. Disabled state lowers contrast and preserves a readable label.
- **Secondary / Ghost / Tertiary:** Paper background with a Newsroom Rule border for secondary actions; ghost actions use text color changes without inventing a new shape.

### Chips

- **Style:** Compact 9999px pill, 2px by 8px padding, label typography, and a Newsprint fill.
- **State:** Selected chips use Editorial Ink or Vandal Gold plus text; status chips add a textual state so color is never the only cue.

### Cards / Containers

- **Corner Style:** 8px for a bounded work surface; repeated table rows do not receive individual rounding.
- **Background:** Paper on a Newsprint canvas.
- **Shadow Strategy:** Ambient Low is optional for the outer work surface only.
- **Border:** 1px Newsroom Rule for tables, controls, and meaningful group boundaries.
- **Internal Padding:** 16px on compact surfaces and 24px on major work sections.

### Inputs / Fields

- **Style:** Paper fill, 1px Newsroom Rule stroke, 6px radius, and 8px by 12px padding.
- **Focus:** Editorial Ink border plus a visible 2px Vandal Gold ring and 2px offset.
- **Error / Disabled:** Alert Red border with nearby error text; disabled controls use Newsprint fill and remain legible.

### Navigation

Use a familiar top bar with a compact product mark and direct workspace links. Labels are 14px medium weight; the active route uses strong ink and a small Vandal Gold signal. On narrow screens, links wrap or collapse into an accessible native disclosure without horizontal clipping. Every link has a visible focus state.

### Evidence Table

The evidence table is the signature component. It uses sticky or clearly separated headers where useful, left-aligned identity columns, right-aligned tabular facts, 1px row rules, restrained hover feedback, and adjacent source or resolution metadata. Horizontal overflow remains keyboard reachable on small screens.

## 6. Do's and Don'ts

### Do:

- **Do** organize screens around an SID's editorial question, with evidence and provenance beside any fact that may be published.
- **Do** use Paper (#ffffff), Newsprint (#f9fafb), and Newsroom Rule (#e5e7eb) to create structure before adding a shadow.
- **Do** reserve Vandal Gold (#eab308) for primary actions, selection, focus, and important attention states.
- **Do** use 14px body copy, 12px labels, right-aligned tabular numerals, and compact 8px to 16px row spacing for scan-friendly data.
- **Do** provide keyboard access, visible focus, reduced-motion behavior, and status text in addition to color to meet WCAG 2.2 AA.

### Don't:

- **Don't** build a fan-facing athletics site around hype, promotional graphics, or game-day spectacle.
- **Don't** produce a generic SaaS dashboard made from interchangeable cards and decorative metrics.
- **Don't** expose a database administration console or implementation details instead of newsroom concepts.
- **Don't** make the interface chatbot-first, obscure evidence, or treat generated prose as authoritative.
- **Don't** imitate sports-broadcast styling when it sacrifices legibility, density, or provenance for visual drama.
- **Don't** use gradients, glass effects, colored side stripes, ornamental display type, or animated decoration.
