---
role: optional design-direction reference
use_when: color must encode state, comparison, hierarchy, or interaction
do_not_use_when: the concept can remain monochrome or color is purely decorative
style_risk: a fixed palette or accent count turns unrelated documents into one house style
---

## Semantic roles

A document may need distinct color roles:

- **Base:** canvas, ink, dividers, and quiet surfaces.
- **Semantic:** status, comparison, category, sequence, or uncertainty.
- **Emphasis:** the limited elements that need priority in the reading path.

The number and temperature of colors follow the evidence, brand constraints, medium, and
design concept. Do not infer them from a document label such as report or dashboard.

## Print / PDF contrast

If the report will be printed or exported to PDF:

- Plan sufficient contrast for the target text size and accessibility requirement.
- Semantic colors must remain distinguishable in greyscale (red vs green fails — pair with shape or label)
- Important emphasis must still read on a monochrome printer when print is in scope.

## Common failure modes

- **Same accent as a rule color** — chrome dissolves into accent
- **Semantic green/red applied to chrome** (e.g., section header in green) — semantic exhausted, deltas no longer pop
- **Dark mode auto-derived from light** — both modes must be intentionally designed; auto-invert reads as careless
- **Color without a documented role** — the builder cannot distinguish meaning from decoration
