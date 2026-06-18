---
role: figure/structure reference for the report plan (not injected anywhere — there is no build stage)
topic: most decisive for data-heavy registers with comparisons and deltas
---

## Three-layer palette

A report palette has three layers, kept structurally distinct:

- **Chrome** (paper, ink, rules, body text): near-neutrals. Never pure `#ffffff` paper or pure `#000000` ink — slightly tinted neutrals (warm or cool near-white paper, warm near-black ink, hairline gray rules) carry more authority
- **Semantic** (data, comparisons, deltas): reserved for meaning, never used for chrome. The comparison pair is assigned ONCE per report and applied to every chart, cell, badge, and legend. Conventional roles: green = gain, red = loss, amber = warning, blue = info
- **Accent** (one hue per register): used sparingly for highlights, badges, hero callouts. Never for body text

## Per-register guidance

- **Audit / Brief**: warm-neutral chrome + single ochre accent. Severity uses semantic red/amber/green sparingly
- **Dashboard**: cooler-neutral chrome + saturated semantic palette for KPI deltas. Subtle bg tints on KPI tiles only
- **IR-deck**: institutional palette (deep navy or single corporate hue) + semantic for QoQ deltas
- **Poster**: high-contrast ink-on-paper pair + single inverted band per section. Color secondary to typography
- **Incident**: muted neutrals + severity colors only (red/amber/green/grey) — no decorative accent

## Print / PDF contrast

If the report will be printed or exported to PDF:

- Body text vs paper: ≥7:1 contrast (WCAG AAA), test in greyscale
- Semantic colors must remain distinguishable in greyscale (red vs green fails — pair with shape or label)
- Accent must still read on a monochrome printer — saturation alone is not signal

## Anti-defaults

- Tailwind's full `slate-200/300/400/500` ramp as chrome — instantly identifies "AI internal-doc" look
- Generic blue (`#3b82f6`, `#2563eb`) as accent — undeliberate
- Purple-to-pink gradient on hero band — kills analytic authority
- Emerald-to-cyan gradient on chart bars — chart-junk
- Pure white paper + pure black ink — careless
- Mid-gray body text (`#6b7280`) to fake hierarchy — use weight, not color (see `craft/typography.md`)
- Different accent per page — register dissolves; one accent per report

## Common failure modes

- **Same accent as a rule color** — chrome dissolves into accent
- **More than 3 saturated hues per surface** — circus
- **Semantic green/red applied to chrome** (e.g., section header in green) — semantic exhausted, deltas no longer pop
- **Dark mode auto-derived from light** — both modes must be intentionally designed; auto-invert reads as careless
- **Accent used on every page** — accent stops anchoring; reserve for the page-defining element
