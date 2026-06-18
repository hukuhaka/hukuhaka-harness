---
role: figure/structure reference for the report plan (not injected anywhere — there is no build stage)
topic: density, alignment, color, typography for data tables
---

## Density

Row height = 1.5–1.8× body line-height. Not taller. Tall row heights (2.5×+) read as space-filler and signal lack of conviction.

Column padding: consistent across rows. Inter-column gap should match horizontal padding (commonly 16–24px on desktop).

Cells should feel dense, not airy. A 6-column 20-row data table is dense material — let it look that way. Loose cell spacing makes data look like a layout draft.

## Rules

- Horizontal rules: hairline 1px light neutral between rows, OR omitted entirely. Thicker (2px, ink-tone) only on header separator and table-bottom
- Vertical rules: omit by default. Alignment carries the column. Use only when grouped columns need visual separation
- Zebra stripes: skip unless density genuinely requires (≥10 columns, or visually-similar text-heavy rows). Even then, one subtle off-paper tone, not alternating saturated bands

## Alignment

- Numbers: right-aligned, `font-variant-numeric: tabular-nums` always — proportional digits in metric content read as careless
- Text: left-aligned. Headers: same alignment as their column
- Currency / units: right-aligned with unit as smaller muted mono suffix (e.g., `$2,345` `M` at 0.85×)
- Mixed-type columns (text + delta number): right-align the number, let the text fill leftward

## Color

- Deltas: gain = green, loss = red. Same pair across every table in the same report. Subtle saturation; reserve high-saturation for the genuine outlier
- Header row: subtle bg tint OR weight bump, not both — avoid heavy banded headers
- Body cells: no bg color unless data semantically demands it (heatmap, status pill). Chrome color in data cells makes data hard to read
- Hover row: optional subtle bg tint in interactive contexts; never bold/border-change on hover

## Typography

- Body text in tables = report body size, or 1–2px smaller, never larger
- Numbers always in mono with tabular-nums
- Header labels: mono uppercase tracked +0.05em if the report chrome uses mono eyebrows; otherwise sentence-case weight 600
- No italic in tables — italic + tabular-nums fights for the eye

## Don'ts

- Row heights at 3× line-height — table looks padded for space, not dense
- Bordered grid (vertical + horizontal rules on every cell) — reads as spreadsheet, not report
- Sentence-case headers with quote-marks — pseudo-formal
- Center-aligned numbers — kills column eye-scan; right-align always
- Inline icons in numeric cells — fights tabular-nums alignment; put icons in a separate small column
