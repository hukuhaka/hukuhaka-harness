---
role: optional anchor-selection reference
use_when: quantitative evidence contains a comparison, change, distribution, relationship, or composition
do_not_use_when: one value or one sentence answers the reader question more clearly
style_risk: choosing from a short chart menu creates repetitive documents
---

## Default

A chart is evidence, not chrome. State the reader question, source fields, relationship,
takeaway, and uncertainty before choosing a chart form. The planner does not choose the
rendering library or implementation technology.

## Message type → chart type

- **Comparison or ranking:** bar, dot plot, lollipop, dumbbell, slope, or matrix.
- **Change over time:** line, step, area, small multiples, or event-overlay.
- **Distribution or uncertainty:** histogram, box, interval, density, or fan chart.
- **Relationship:** scatter, connected scatter, bubble, or correlation matrix.
- **Composition or contribution:** stacked bar, mosaic, treemap, or waterfall.

Select from the relationship and reading task, not from a desire for variety.

## Axes

- Label both axes with units (`Latency (ms)`, `Throughput (req/s)`). Unitless axes read as careless
- Tabular-nums on all tick labels (`font-variant-numeric: tabular-nums`)
- Keep tick density low enough to scan at the target size.
- Origin: include zero unless explicitly framing a delta range. If you crop the axis, annotate the crop (`// y-axis starts at 80%`) — silent cropping misleads
- Use only the gridlines needed to make comparisons accurately.

## Palette

- Keep semantic roles consistent across the document.
- Use as many distinguishable encodings as the evidence requires, but no more.
- Never assign meaning to color alone; pair it with a label, shape, pattern, or position.

## Annotation

Annotate the finding, inflection, comparison, or uncertainty when the reader would otherwise
have to infer it. Exploratory and lookup charts may not have one predetermined finding.

## Don'ts

- Decorative depth or effects that imply values not present in the data
- Too many segments to compare accurately in an angle- or area-based chart
- Time-series with x-axis labels `1, 2, 3, 4` — show actual dates
- Stacked bars without category total annotation — reader has to do mental math
- "Smooth" line interpolation on noisy data — misleads about between-point values
- Axis labels too small or low-contrast to read at page-thumbnail zoom
