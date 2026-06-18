---
role: figure/structure reference for the report plan (not injected anywhere — there is no build stage)
topic: most decisive for page-as-unit registers needing scan rhythm and density variation
---

## 8-tier scale

Use a single 8-tier spacing scale, never one-off values. Every spacing value resolves to one tier:

- **4 / 8 / 12 px** (tiers 1-3): inline gap, tight badge padding, label-value gap, tile and table-cell padding
- **16 / 24 / 32 px** (tiers 4-6): paragraph spacing, button padding, section sub-block gap, column gap, callout outer
- **48 / 72 px** (tiers 7-8): section gap, page section break

Off-scale values (37px, 52px, 19px) identify hand-tuning failure — pick the nearest tier.

## Page margins (per register, page-as-unit)

| Register | Horizontal | Vertical | Reason |
|---|---|---|---|
| **Audit / Brief** | 8% viewport | 6% viewport | reading comfort, prose-led |
| **Dashboard** | 2-3% all sides | (single surface) | maximize data surface |
| **IR-deck (16:9)** | 5% all sides | 5% all sides | slide breathing room |
| **Poster** | 3% all sides | 3% all sides | density wins |
| **Incident** | 6% horizontal | 5% vertical | timeline-led |

Print/PDF rendering: use mm-based margins for final export (e.g., 18mm horizontal on A4 audit).

## Vertical rhythm

- Body line-height: 1.45-1.55; headline 1.1-1.2 (display) or 1.25-1.35 (sub-display)
- Major section gaps from the top tiers (48/72px); sub-blocks within a section from 24/32px
- Section gap MUST be larger than paragraph gap by at least 2 tiers — otherwise sections dissolve

## Scan rhythm (density variation per page)

A scan-read artifact needs density variation per page: **dense bands** (data table, chart cluster, KPI strip) alternating with **breathable bands** (single hero number on a near-empty band, one-line opener). Pages where every band is the same density read as uniform gray and the eye skips — at least one breathable band per page. The breathable band is not whitespace for its own sake: it carries one element with high visual weight (oversized number, single sentence, prominent figure). Empty padding is decoration; weighted breath is content.

## Anti-defaults and failure modes

- Tailwind default `space-y-4` everywhere — uniform rhythm = no scan path
- Off-scale ad-hoc values (37px, 52px) — visual jitter
- Equal padding all 4 sides on every container (padding-y = padding-x everywhere) — square containers kill rhythm and hierarchy
- Section gap = paragraph gap — sections dissolve into prose
- Single space scale for type AND layout — mixing scales breaks rhythm
- No tier-7/8 gap on the page — page reads as a single dense block
- Tier-1/2 spacing inside body prose — text feels cramped
- Margin-collapse not understood — vertical gaps double-count or disappear under flex/grid
- Edge-to-edge content on wide viewports — long lines unreadable; cap measure (see `craft/typography.md`)
