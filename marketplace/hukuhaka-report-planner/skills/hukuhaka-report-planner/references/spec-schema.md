# spec.md schema — the report plan

This skill produces ONE artifact: a **plan** recorded at

```
.claude/reports/<short-name>/spec.md
```

No `report.html`, no screenshots — building is a separate, unconstrained step that happens
*after* this skill, driven by the plan. The plan is the deliverable.

`<short-name>` is derived in Stage 1 from the subject (lowercase, hyphenated, ≤24 chars,
e.g. `vit-benchmark`, `terraform-flow`, `q1-earnings`). spec.md is born at Stage 0 under
`.claude/reports/tmp-draft/` with the `## Frame` block alone; Stage 1 overwrites it with
Frame (carried forward) + `## Contents`, then renames the directory to `<short-name>`.

## spec.md — full template

```markdown
# <title> — report plan — <YYYY-MM-DD>

## Frame

- purpose: <what the report is for — 보고용 발표 | 개인 정리 | 공유 문서 | go/no-go 논의 | ...>
- audience: <who reads it, in what context, for what decision or lookup>
- prose level: <brief — figure 중심, 설명 최소 | full — 설명 산문 포함>
- design direction: <one line — palette temperature, canvas, accent strategy, optional reference look; e.g. "cool-neutral, pure-white canvas, single electric-blue accent, fintech-crisp">
- build preferences: <optional; 1-3 soft heuristics using "prefer X over Y"; e.g. "prefer one accent hue with lightness/saturation variation over many unrelated hues; prefer figure-first layouts over card grids">
- form: <web doc | deck | print PDF>   # optional — omit if undecided

## Contents

- 01 <Section / tab title> — figures: <timing diagram | diff table | KPI strip | bar chart | code block | ...>; note: <one line, optional>
- 02 <Section / tab title> — figures: <...>
- 03 <Section / tab title> — figures: <...>
- ...
- out of scope: <what the report deliberately excludes, one line>   # optional
```

That is the whole file. There are no provenance tags, no register/mode axes, no build log.

## What each block is for

- **Frame** — the four required lines (plus optional `build preferences` and `form`) that shape every later decision.
  `prose level` is the lever the user reaches for with "나만 볼거라 설명 글은 간략하게"
  (→ `brief`) vs "보고용" (→ `full`). `design direction` is the taste lever — one line of
  visual intent handed to whoever builds, NOT a token sheet. It exists to prevent the
  generic-AI / warm-yellowish default the user has rejected. `build preferences` are soft
  "prefer X over Y" heuristics for likely build drift, not CSS tokens or mandatory visual
  rules.
- **Contents** — the section/tab outline. Each line names a section AND the concrete figures
  that section needs, derived from the actual material (not guessed). This is the heart of
  the plan: "이 자료엔 timing diagram·diff table·throughput bar가 필요하고, 섹션은
  01 Overview · 02 Setup · 03 Results …" lands here.

## Rules

- **Frame rule (Stage 0)**: the `## Frame` block holds the four required lines (`purpose`,
  `audience`, `prose level`, `design direction`), each non-empty. `build preferences` and
  `form` are optional. spec.md is born at Stage 0 with this block alone.
- **Contents rule (Stage 1)**: at least one `- NN <title>` section line, each naming its
  figures. The figure list is derived from the material — if a section names no anchor, it
  is prose-only and should be reconsidered or merged.
- **Figures are derived, not defaulted**: the plan proposes the figures the material calls
  for (a timing series → timing diagram; before/after → diff table; a ranking → bar). Do not
  attach a figure type the data cannot support, and do not leave a data-rich section with no
  figure.
- **Design direction is a brief lever, not a style sheet**: one line constraining
  temperature/canvas/accent. The eventual builder interprets it; the plan does not enumerate
  CSS tokens.
- **Build preferences are soft heuristics, not gates**: use `prefer X over Y` language to
  guide the eventual builder away from generic defaults without turning the plan into a CSS
  spec. Keep them optional and short.
- **No mode, no register, no determinism table.** Structure is proposed freely from the
  material each time. There is no argument/reference fork.
- **The plan stops at spec.md.** This skill does not build, screenshot, or self-test the
  artifact. Handoff to a design skill (`hallmark` / `frontend-design`) or a normal build turn
  is the user's next, unconstrained step.
- `validate-spec.sh` is an **optional self-check** (Frame fields present + ≥1 Contents
  section), not a fail-closed gate. Nothing blocks the write.
