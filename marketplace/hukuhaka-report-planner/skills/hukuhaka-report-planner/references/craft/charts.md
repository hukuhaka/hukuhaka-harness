---
role: figure/structure reference for the report plan (not injected anywhere — there is no build stage)
topic: argument-leaning — every chart must carry a finding
---

## Default

A chart is content, not chrome. Every chart answers a question prose cannot answer as efficiently. If the chart can be replaced by one sentence, delete the chart. Build charts as CSS bars or hand-authored inline SVG — every axis, palette, label, and annotation choice is intentional. Library defaults identify the report as a template-of-template instantly.

## Message type → chart type

- RANKING → bar (horizontal when category names are long)
- CHANGE-OVER-TIME → line
- PART-TO-WHOLE → stacked bar
- Pick the chart from the message, never from variety. Two adjacent bar charts beat one forced pie.

## Axes

- Label both axes with units (`Latency (ms)`, `Throughput (req/s)`). Unitless axes read as careless
- Tabular-nums on all tick labels (`font-variant-numeric: tabular-nums`)
- Tick density: ≤7 major ticks per axis; more = noise
- Origin: include zero unless explicitly framing a delta range. If you crop the axis, annotate the crop (`// y-axis starts at 80%`) — silent cropping misleads
- Gridlines: hairline 1px, light neutral, horizontal only. Vertical gridlines are noise unless the chart is time-series with date ticks

## Palette

- 2-series chart → one committed comparison color pair (winner-loser, baseline-proposed). Same pair across every chart in the same report
- ≥3 series → one accent + greyscale shades. Rainbow palettes are forbidden
- Categorical (not comparative) → ordinal greyscale + one accent for the focus category; single-series → one accent, neutral chrome
- Never assign meaning to color alone — pair with shape, label, or position

## Annotation

For every chart, mark at least one of: the bar that matters, the inflection, the crossover, the outlier. Annotation = short text label + hairline rule pointing to the data point, NOT a callout balloon with shadow. A chart with no annotation conveys no specific finding.

## Don'ts

- 3D bars, drop-shadowed bars, gradient fills on data, rainbow palettes, chart-junk borders
- Charting-library default colors (e.g., `rgba(54, 162, 235)`) — instantly identifies AI default
- Pie chart with >5 slices → use horizontal bar instead
- Time-series with x-axis labels `1, 2, 3, 4` — show actual dates
- Stacked bars without category total annotation — reader has to do mental math
- "Smooth" line interpolation on noisy data — misleads about between-point values
- Legend when direct labels fit next to each line/bar — direct-label and drop the legend
- Axis labels too small or low-contrast to read at page-thumbnail zoom
