---
name: hukuhaka-report-planner
description: "Plan a report before building it: look at the material, propose the concrete figures it needs (timing diagram, diff table, KPI strip, bar chart, hand-authored diagram, code block), propose a section/tab outline that carries them (01 Overview · 02 … · 03 …), refine with the user, and record the plan to spec.md. Captures the user's levers — purpose, audience, prose level (brief vs full), design direction (the look/taste, to avoid generic-AI output) — without imposing a rigid pipeline. Triggers — ANY of: report, writeup, summary, audit, benchmark, comparison, analysis, brief, deck, dashboard, slides, presentation, poster, memo, postmortem, retrospective, scorecard, recap, overview, findings, evaluation, review, walkthrough, handbook, explainer, technical writeup, executive summary, status update, incident report, code structure doc, project flow doc. Output: a recorded plan (spec.md) — NOT the built HTML. Building is a separate, unconstrained step the user runs afterward (e.g. hand the plan to hallmark / frontend-design). Skip when: the user wants the artifact built immediately with no planning, a long-form essay, blog post, marketing copy, API reference, or changelog list."
---

This skill **plans** a report — it does not build it. The job is to look at the material,
figure out what the report should contain (which figures, which sections), agree that with
the user, and record it. Building the HTML is a separate, unconstrained step that happens
afterward, driven by the recorded plan.

This is a deliberate scope: the previous version was a gated build pipeline that produced
mediocre, over-constrained output. The valuable part was always the *thinking up front* —
"이 자료엔 timing diagram·diff table가 필요하고, 섹션은 01 Overview · 02 Setup · 03 Results
정도" — so that is all this skill does now. No registers, no modes, no per-page gates, no
self-test battery. Two light stages, then a handoff.

## Workflow

Two stages. Open the stage file BEFORE executing it; do not work from memory.

| # | File | Purpose | Verification gate |
|---|---|---|---|
| 0 | `stages/0-frame.md` | Brief look → propose a light Frame (purpose / audience / prose level / design direction; form optional); spec.md born at `.claude/reports/tmp-draft/` | User confirms/edits the Frame in one exchange |
| 1 | `stages/1-plan.md` | Read deeply → propose the figure inventory + section/tab outline → refine with the user → record spec.md → hand off | User confirms the figures + outline; then the skill stops (build is a separate turn) |

The skill **ends when the plan is recorded.** It does not produce `report.html`, screenshots,
or a self-test. If the user then says "build it", that is a new, unconstrained turn — the
plan is the contract, but none of the old pipeline's gates/chunks/tests apply.

## Output

```
.claude/reports/<short-name>/
  └── spec.md          ← the plan: ## Frame + ## Contents
```

`spec.md` is the only artifact. See `references/spec-schema.md` for the exact shape. It holds
a **Frame** (the shaping levers) and **Contents** (the section outline with per-section
figures). No build log, no provenance tags, no axis table.

## Report Thinking (what the plan captures)

- **Purpose + audience** — what the report is for and who reads it. These set everything else.
- **Prose level** — `brief` (figure-centric, minimal text — "나만 볼거라 간략하게") vs `full`
  (explanatory prose included — "보고용"). The single biggest lever on how the report reads.
- **Design direction** — one line of visual intent (palette temperature, canvas, accent
  strategy, optional reference look). The taste lever, captured so the eventual build does
  not fall back to the generic-AI / warm-yellowish look the user rejects. Not a token sheet.
- **Figure inventory** — the concrete figures the *material* calls for, derived from the
  shape of the data (a metric over an ordered axis → line; a trace over time → timing diagram;
  before/after → diff table; ranking → bar; structure → hand-authored diagram). The center of
  the plan.
- **Section/tab outline** — the figures grouped into a natural reading order, proposed from
  the material (not a Background/Methodology/Conclusion template).

## Notes for the build (carried in the plan / handoff)

When the plan is eventually built, these keep it from generic-AI slop — record them in the
handoff so whoever builds (hallmark / frontend-design / a normal turn) honors them:

- Hand-author SVG for diagrams — never Mermaid, never auto-icons.
- Charts are CSS bars / inline SVG — no charting library. RANKING → bar, OVER-TIME → line,
  PART-TO-WHOLE → stacked.
- Avoid the generic Tailwind-card look (slate borders, rounded-2xl everywhere, muted gray,
  Inter-by-default), rainbow/3D/gradient chart styling, centered marketing-hero layouts,
  and equal-weight flat hierarchy.
- `font-variant-numeric: tabular-nums` on metrics; font chains end in a generic family.
- The `design direction` line governs palette/canvas/accent — hold the whole document to it.

## Implementation Notes

- **Derive figures, don't default them.** Propose the figure a piece of data can actually
  support; never leave a data-rich section figure-less, never bolt on a figure the data
  cannot back. This is the skill's main value.
- **Don't build inside the skill.** Stage 1 records the plan and stops. Pixels are a separate
  turn. Offering to build is fine; doing it under this skill's name is not.
- **Verify named entities against source.** Any command, path, class, version, or count that
  will appear in the report must be confirmed by reading/grepping the source before it lands
  in the plan — memory is not verification.
- **No mode/register/Hero/Spine machinery.** Removed on purpose. Structure is proposed freely
  from the material each time; the only fixed shape is Frame + Contents.

## References

- `stages/0-frame.md`, `stages/1-plan.md` — the two-stage protocol; open each on entry
- `references/spec-schema.md` — spec.md template (Frame + Contents); contract for `scripts/validate-spec.sh`
- `references/craft/` — figure/structure reference (what makes a good timing diagram, diff
  table, chart, callout, diagram). Used to propose figure types and describe them concretely;
  reference notes, not a brief to inject (there is no build stage).
- `references/fixtures/{source}/` — captured aesthetic systems (currently `fixtures/figma/`),
  useful when describing a `design direction`. **Mine for ideas, never clone.**
- `scripts/validate-spec.sh [<spec.md>]` — optional self-check (Frame fields + ≥1 Contents
  section). Not a gate; nothing blocks the write.

Remember: the deliverable is a good *plan* — the right figures and a sound outline, agreed
with the user. Building is someone else's next move.
