---
stage: 1
purpose: read the material deeply, propose the figures it needs + a section/tab outline, refine with the user, and record the finished plan to spec.md — then hand off
prereq: Stage 0 Frame block committed in .claude/reports/tmp-draft/spec.md
deliverable: spec.md overwritten (Frame carried forward + filled Contents); directory renamed tmp-draft → <short-name>
verification_gate: user confirms the figures + section outline; iterate freely
---

## What this stage does

This is the substance of the skill — and the moment the user described wanting:

> "실험 보니까 필요한 figure: timing diagram, diff table, throughput bar. 섹션은
> 01 Overview · 02 Setup · 03 Results · 04 Analysis 정도. 이렇게 갈까요?"

Stage 1 reads the actual material, **derives the figures it calls for**, proposes a
section/tab outline carrying those figures, refines with the user, records the plan, and
stops. There is no register, no mode, no Hero/Spine fork, no axis receipt — structure is
proposed freely from what the material actually contains.

The skill ends here. Building the HTML is a separate, unconstrained step (see Handoff).

## Required reading

- `.claude/reports/tmp-draft/spec.md` — the Stage-0 Frame (re-read at stage start)
- `references/spec-schema.md` — the Contents block shape this stage produces
- `references/craft/` — figure/structure reference: what makes a good timing diagram, diff
  table, chart, callout, etc. Use it to propose figure *types* that fit the data, and to
  describe each figure concretely. (These are reference notes, not a brief to inject — there
  is no build stage here.)

## Process

### 1a — Deep read + figure inventory

1. **Re-read the Frame.** `prose level`, `design direction`, and any optional
   `build preferences` shape what you propose: `brief` → lean harder on figures, minimal
   prose notes; `full` → sections carry explanatory text too. Treat build preferences as
   soft defaults, not gates.

2. **Read the material deeply** — the experiment results / code / data / findings — enough to
   know what it actually contains and what each part can support. Confirm named entities you
   may cite against source; memory is not verification.

3. **Derive the figure inventory.** For the material, list the concrete figures it calls for,
   each tied to what data backs it. Derive the *type* from the shape of the data:
   - a metric over an ordered axis (time, batch size, training step) → **line chart**
   - events / stages over time, a pipeline trace → **timing diagram** (sequence / waterfall)
   - a distribution of values → **histogram**
   - before/after, config delta → **diff table**
   - ranking, throughput, counts → **bar chart**
   - composition, share → stacked bar / part-to-whole
   - structure, flow, pipeline → **hand-authored diagram** (swimlane, boxes-and-arrows)
   - key metrics → **KPI strip**; verbatim config/output → **code block**; tabular facts → **table**
   Do not attach a figure a piece of data cannot support; do not leave a data-rich part with
   no figure. Hand-authored SVG for diagrams — never Mermaid.

### 1b — Section/tab outline

4. **Propose the outline.** Group the material into sections/tabs in a natural order
   (`01 Overview · 02 Setup · 03 Results · 04 Analysis` …). Each section names the concrete
   figures from the inventory that live in it. Sections are proposed from the material's
   shape — there is no fixed template to fill.

5. **Derive `<short-name>`** from the subject: lowercase kebab-case ≤24 chars, first 1-2
   nouns (`vit-benchmark`, `terraform-flow`, `q1-earnings`).

### 1c — Propose, refine, record

6. **Show the proposal and discuss.** Present the figure inventory + section outline together:
   "필요한 figure는 …, 섹션은 …. 이렇게 갈까요?" The user steers freely — examples of the
   moves to expect (handle each, then re-show the updated plan):
   - "그렇게 하고 전체적으로 보고용" → set/confirm `purpose` + `prose level: full`
   - "나만 볼거라 설명 글 간략하게" → `prose level: brief`
   - "좋은데 02에 메모리 그래프 추가" → add that figure to section 02
   - "03이랑 04 합쳐" / "Setup은 빼" → restructure
   - "디자인은 더 차갑게" → update `design direction`
   - "색은 한 계열 안에서 가자" → add/update `build preferences`
   Iterate until the user is satisfied. There is no fixed round limit and no fail-closed gate.

7. **Record the plan.** On confirm:
   - Rename `.claude/reports/tmp-draft/` → `.claude/reports/<short-name>/`.
   - Overwrite spec.md (full-file Write): `## Frame` carried forward (with any updates from
     the discussion) + the filled `## Contents` block per `references/spec-schema.md`.
   - Optionally run `scripts/validate-spec.sh .claude/reports/<short-name>/spec.md` as a
     self-check (Frame fields + ≥1 section). It does not gate; it just catches an omission.

### 1d — Handoff (the skill ends)

8. Tell the user the plan is recorded and what comes next — **without building it**:

   > 플랜 기록 완료 → `.claude/reports/<short-name>/spec.md`. 빌드하려면 이 플랜을
   > `hallmark` 또는 `frontend-design`로 넘기거나, 그냥 "이대로 빌드해줘" 하시면 됩니다.
   > (빌드는 이 스킬 밖이라 제한 없이 진행됩니다.)

   Do not start building inside this skill. If the user immediately says "build it", that is a
   new, unconstrained turn — the plan is the contract, but no gates, chunks, or self-tests
   from the old workflow apply.

## Output (the plan)

```
SHORT-NAME: <kebab-case>
FIGURES: <timing diagram · diff table · throughput bar · ...>
CONTENTS:
  01 <Section> — figures: <...>
  02 <Section> — figures: <...>
  ...
  out of scope: <one line>            (optional)
SPEC: .claude/reports/<short-name>/spec.md recorded (Frame + Contents)
```

## Failure modes

- **Attaching figures the data can't support** — a "timing diagram" with no time series, a
  "diff table" with nothing to diff. The inventory is derived, not decorative.
- **Leaving a data-rich section figure-less** — a Results section that is all prose hides the
  data the report exists to show.
- **Defaulting to a template outline** (Background / Methodology / Conclusion) instead of
  proposing from the material — the sections should reflect what this material actually is.
- **Building inside the skill** — Stage 1 records the plan and stops. Pixels are a separate turn.
- **Re-introducing mode/register/Hero/Spine machinery** — deleted on purpose; structure is free.
- Skipping the directory rename, or skipping the disk write — the recorded plan is the deliverable.
