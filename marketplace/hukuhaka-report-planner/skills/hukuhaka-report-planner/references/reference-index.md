# Reference index

Use this file only after creating a reference-free design concept. Select zero to three
craft files that answer a specific unresolved problem. Do not read the directory wholesale.

| Need | Read | Do not use it to decide |
|---|---|---|
| comparison, change, distribution, relationship, composition | `craft/charts.md` | overall page style |
| distribution shape, tails, correlation, two-dimensional grids | `craft/plots.md` | whether the evidence supports a statistical claim |
| events, spans, traces, waterfalls, incident chronology | `craft/timing-diagrams.md` | implementation technology |
| process, sequence, dependency, topology, state | `craft/diagrams.md` | implementation technology |
| lookup, matrix comparison, dense facts | `craft/tables.md` | typography or palette |
| source excerpt, config, command, diff | `craft/code-blocks.md` | document structure |
| central metric or status summary | `craft/kpi-tiles.md` | whether every page needs a large number |
| caveat, evidence note, recommendation, quotation | `craft/callouts.md` | decorative emphasis |
| interface state, rendered output, or tool result as evidence | `craft/screenshots.md` | whether the underlying text should be quoted instead |
| entry surface for a deck, poster, or long document | `craft/cover.md` | a mandatory hero layout |
| slide grammar, per-slide density, deck reading distance | `craft/decks.md` | the document job or trunk |
| live status surface, staleness, alert-state encoding | `craft/dashboards.md` | whether the job is really monitoring |
| semantic color and accessible state encoding | `craft/color.md` | a fixed palette or accent count |
| density, grouping, responsive rhythm | `craft/spacing.md` | exact token values |
| reading voice, hierarchy, numeric or code roles | `craft/typography.md` | a fixed font pairing |
| alignment axes, grid, anchor placement, section wayfinding | `craft/layout.md` | exact grid or column values |
| design-direction vocabulary after a reference-free concept exists | `directions.md` | the document job, structure, or source facts |

## Selection record

For each selected reference, write:

```yaml
source:
borrowed mechanism:
why it fits:
translation for this document:
rejected mechanism:
clone risk:
```

An external style target is off by default. When the user explicitly supplies a `DESIGN.md`,
record its path in Design Direction after forming the reference-free concept. Read its
frontmatter and overview first, then only the sections that resolve a named design problem.
Record what must not transfer; do not copy trademarks, proprietary assets, or irrelevant
website chrome into the artifact plan.
