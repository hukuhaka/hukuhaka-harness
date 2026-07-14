# Reference index

Use this file only after creating a reference-free design concept. Select zero to three
craft files that answer a specific unresolved problem. Do not read the directory wholesale.

| Need | Read | Do not use it to decide |
|---|---|---|
| comparison, change, distribution, relationship, composition | `craft/charts.md` | overall page style |
| process, sequence, dependency, topology, state | `craft/diagrams.md` | implementation technology |
| lookup, matrix comparison, dense facts | `craft/tables.md` | typography or palette |
| source excerpt, config, command, diff | `craft/code-blocks.md` | document structure |
| central metric or status summary | `craft/kpi-tiles.md` | whether every page needs a large number |
| caveat, evidence note, recommendation, quotation | `craft/callouts.md` | decorative emphasis |
| entry surface for a deck, poster, or long document | `craft/cover.md` | a mandatory hero layout |
| semantic color and accessible state encoding | `craft/color.md` | a fixed palette or accent count |
| density, grouping, responsive rhythm | `craft/spacing.md` | exact token values |
| reading voice, hierarchy, numeric or code roles | `craft/typography.md` | a fixed font pairing |

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

`references/fixtures/` is off by default. Open a fixture only when the user explicitly asks
for a style study or supplies it as a target. Read its overview first, select at most one
subsystem, and record what must not transfer.
