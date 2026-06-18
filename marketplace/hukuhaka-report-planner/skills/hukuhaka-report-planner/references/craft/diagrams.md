---
role: figure/structure reference for the report plan (not injected anywhere — there is no build stage)
topic: hand-built SVG diagrams — the primary anchor for structure, flow, and pipeline figures
---

## Hand-author rule

Never Mermaid in this context. Auto-generated diagrams read as filler — the auto-layout is the convergence point. Hand-author every diagram in inline `<svg>`. This rule is absolute: if a diagram is too complex to hand-author, it is probably too complex for the report — decompose.

## Stroke discipline

- All structural strokes: 1.5px OR 2px — pick ONE per diagram, use everywhere. Mixed weights read as accidental
- Stroke color: `currentColor` (inherits ink) for structural lines; one literal accent color for the highlighted path only
- Stroke-linecap: `round` for organic, `square` for technical schematics. Pick once per diagram
- Never stroke + fill the same shape unless deliberately representing nested state — pick one

## Color

- Diagram chrome: ink-on-paper, hairline rules, no fills except severity boxes
- At most ONE accent color per diagram (the highlighted path, the inflection node)
- Severity boxes (rare): reuse the report's semantic palette, never new colors

## Labels

- Node labels: mono at body size or 1–2px smaller
- Sub-labels / annotations: serif italic at body size minus 2–3px — separates annotation from primary label
- Edge labels: mono at body size minus 2–3px, placed mid-edge over a paper-background slug so the label sits cleanly over the line
- Tabular-nums on any numeric label (counts, throughput)

## Annotation

For every diagram, mark at least one of: the critical path, the bottleneck, the changed component, the entry point. Annotation = short mono label + hairline rule pointing to the element. A diagram with no accent path reads as inert — nothing to follow.

Every figure needs a serif italic caption at body-size-minus-2 explaining what the reader is looking at.

## Don'ts

- Mermaid in any form, ever
- Library iconography (Lucide, Feather, Font Awesome) as diagram nodes — converges to "tech blog hero"
- Drop-shadowed boxes with rounded corners — generic
- 3D rendering, isometric without reason, gradient fills on nodes — chart-junk
- All-caps labels in body diagrams — shouting
- Animated SVG (rotating, pulsing) — kills scan; this is a static artifact
- Sans labels without tabular-nums — proportional digits in counts misalign
- Leader lines crossing each other to reach labels outside the figure — restructure the layout
